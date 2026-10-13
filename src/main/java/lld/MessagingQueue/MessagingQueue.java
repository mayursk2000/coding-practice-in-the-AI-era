import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;


public class MessageBroker{
    public static class Message {
        public final long id;
        public final String topic;
        public final String payload;

        Message(long id, String topic, String payload){
            this.id = id;
            this.topic = topic;
            this.payload = payload;
        }

        @Override
        public String toString(){
            return id +":" + payload;
        }
    }

    private static class QueueItem{
        final Message message;
        int attempts;

        QueueItem(Message message){
            this.message = message;
        }
    }

    private static class Delivery{
        final QueueItem item;
        final String consumerId;
        final long expiresAtNanos;

        Delivery(
                QueueItem item,
                String consumerId,
                long expiresAtNanos) {

            this.item = item;
            this.consumerId = consumerId;
            this.expiresAtNanos = expiresAtNanos;
        }
    }


    private static class TopicState {

        final Deque<QueueItem> ready =
                new ArrayDeque<>();

        final Map<Long, Delivery> inFlight =
                new HashMap<>();

        final Set<String> consumers =
                new HashSet<>();

        final ReentrantLock lock =
                new ReentrantLock();
    }

    //listing all my topics here
    private final Map<String, TopicState> topics = new ConcurrentHashMap<>();

    //consumer to topic mapping
    private final Map<String, String> consumerTopics = new ConcurrentHashMap<>();

    private final Map<Long, TopicState> inFlightIndex =
            new ConcurrentHashMap<>();

    private final AtomicLong nextMessageId = new AtomicLong(1);

    private final long visibilityTimeOutNanos;


    public MessageBroker(long visibilityTimeoutMillis) {
        this.visibilityTimeoutNanos =
                visibilityTimeoutMillis * 1_000_000L;
    }


    public long publish(
            String topic,
            String payload) {

        TopicState state =
                topics.computeIfAbsent(
                        topic,
                        ignored -> new TopicState()
                );

        long id =
                nextMessageId.getAndIncrement();

        Message message =
                new Message(id, topic, payload);

        state.lock.lock();

        try {
            state.ready.addLast(
                    new QueueItem(message)
            );
        } finally {
            state.lock.unlock();
        }

        return id;
    }

    public void subscribe(
            String topic,
            String consumerId) {

        TopicState state =
                topics.computeIfAbsent(
                        topic,
                        ignored -> new TopicState()
                );

        state.lock.lock();

        try {
            state.consumers.add(consumerId);
            consumerTopics.put(
                    consumerId,
                    topic
            );
        } finally {
            state.lock.unlock();
        }
    }

    public Message poll(String consumerId) {

        String topic =
                consumerTopics.get(consumerId);

        if (topic == null) {
            throw new IllegalArgumentException(
                    "consumer not subscribed"
            );
        }

        TopicState state =
                topics.get(topic);

        state.lock.lock();

        try {
            requeueExpired(
                    state,
                    System.nanoTime()
            );

            QueueItem item =
                    state.ready.pollFirst();

            if (item == null) {
                return null;
            }

            item.attempts++;

            Delivery delivery =
                    new Delivery(
                            item,
                            consumerId,
                            System.nanoTime()
                                    + visibilityTimeoutNanos
                    );

            state.inFlight.put(
                    item.message.id,
                    delivery
            );

            inFlightIndex.put(
                    item.message.id,
                    state
            );

            return item.message;

        } finally {
            state.lock.unlock();
        }
    }

    public boolean ack(long messageId) {

        TopicState state =
                inFlightIndex.get(messageId);

        if (state == null) {
            return false;
        }

        state.lock.lock();

        try {
            Delivery delivery =
                    state.inFlight.remove(messageId);

            if (delivery == null) {
                return false;
            }

            inFlightIndex.remove(
                    messageId,
                    state
            );

            return true;

        } finally {
            state.lock.unlock();
        }
    }

    

    
}