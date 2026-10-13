enum JobState {
    SCHEDULED,
    RUNNING,
    COMPLETED,
    CANCELLED,
    FAILED
}

class Job {
    long id;
    Runnable task;

    long runAt;
    JobState state;

    Job(long id, Runnable task, long runAt) {
        this.id = id;
        this.task = task;
        this.runAt = runAt;
        this.state = JobState.SCHEDULED;
    }
}