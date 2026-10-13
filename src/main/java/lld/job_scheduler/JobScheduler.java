import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

public class JobScheduler {

    private final PriorityQueue<Job> queue =
            new PriorityQueue<>(
                    Comparator.comparingLong(j -> j.runAt)
            );

    private final Map<Long, Job> jobs =
            new HashMap<>();

    private final AtomicLong nextId =
            new AtomicLong(1);

    private final ReentrantLock lock =
            new ReentrantLock();

    private final Condition changed =
            lock.newCondition();

    private volatile boolean shutdown = false;

    private static class Job {
        long id;
        Runnable task;
        long runAt;

        JobState state =
                JobState.SCHEDULED;

        Job(
                long id,
                Runnable task,
                long runAt) {

            this.id = id;
            this.task = task;
            this.runAt = runAt;
        }
    }

    private enum JobState {
        SCHEDULED,
        RUNNING,
        COMPLETED,
        CANCELLED,
        FAILED
    }

    // ------------------------------------------------
    // schedule
    // ------------------------------------------------

    public long schedule(
            Runnable task,
            long runAt) {

        long id =
                nextId.getAndIncrement();

        Job job =
                new Job(id, task, runAt);

        lock.lock();

        try {
            Job previousFirst =
                    queue.peek();

            jobs.put(id, job);
            queue.offer(job);

            /*
             * If this job became the earliest job,
             * wake the scheduler.
             */
            if (previousFirst == null
                    || job.runAt < previousFirst.runAt) {

                changed.signal();
            }

            return id;

        } finally {
            lock.unlock();
        }
    }

    // ------------------------------------------------
    // cancel
    // ------------------------------------------------

    public boolean cancel(long jobId) {

        lock.lock();

        try {
            Job job =
                    jobs.get(jobId);

            if (job == null) {
                return false;
            }

            if (job.state != JobState.SCHEDULED) {
                return false;
            }

            job.state =
                    JobState.CANCELLED;

            /*
             * Lazy removal:
             * don't remove from heap immediately.
             */
            changed.signal();

            return true;

        } finally {
            lock.unlock();
        }
    }

    // ------------------------------------------------
    // reschedule
    // ------------------------------------------------

    public boolean reschedule(
            long jobId,
            long newRunAt) {

        lock.lock();

        try {
            Job old =
                    jobs.get(jobId);

            if (old == null
                    || old.state
                    != JobState.SCHEDULED) {

                return false;
            }

            /*
             * Cancel old heap entry.
             */
            old.state =
                    JobState.CANCELLED;

            /*
             * New heap entry with same logical id.
             */
            Job replacement =
                    new Job(
                            jobId,
                            old.task,
                            newRunAt
                    );

            jobs.put(
                    jobId,
                    replacement
            );

            queue.offer(replacement);

            changed.signal();

            return true;

        } finally {
            lock.unlock();
        }
    }

    // ------------------------------------------------
    // scheduler loop
    // ------------------------------------------------

    public void workerLoop()
            throws InterruptedException {

        while (true) {

            Job job;

            lock.lock();

            try {

                while (true) {

                    if (shutdown) {
                        return;
                    }

                    removeCancelledJobs();

                    if (queue.isEmpty()) {
                        changed.await();
                        continue;
                    }

                    Job next =
                            queue.peek();

                    long now =
                            System.currentTimeMillis();

                    long waitTime =
                            next.runAt - now;

                    if (waitTime > 0) {

                        changed.awaitNanos(
                                waitTime
                                * 1_000_000L
                        );

                        continue;
                    }

                    job =
                            queue.poll();

                    /*
                     * Could have been cancelled
                     * after becoming heap head.
                     */
                    if (job.state
                            == JobState.CANCELLED) {

                        continue;
                    }

                    job.state =
                            JobState.RUNNING;

                    break;
                }

            } finally {
                lock.unlock();
            }

            /*
             * Very important:
             * run job OUTSIDE scheduler lock.
             */
            try {

                job.task.run();

                lock.lock();

                try {
                    job.state =
                            JobState.COMPLETED;

                    /*
                     * Only remove if this is still
                     * the current generation.
                     */
                    if (jobs.get(job.id) == job) {
                        jobs.remove(job.id);
                    }

                } finally {
                    lock.unlock();
                }

            } catch (Throwable t) {

                lock.lock();

                try {
                    job.state =
                            JobState.FAILED;

                } finally {
                    lock.unlock();
                }
            }
        }
    }

    private void removeCancelledJobs() {

        while (!queue.isEmpty()
                && queue.peek().state
                == JobState.CANCELLED) {

            queue.poll();
        }
    }

    public void shutdown() {

        shutdown = true;

        lock.lock();

        try {
            changed.signalAll();
        } finally {
            lock.unlock();
        }
    }
}