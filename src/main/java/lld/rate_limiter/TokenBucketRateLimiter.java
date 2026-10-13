import java.util.concurrent.ConcurrentHashMap;

public class TokenBucketRateLimiter{
    private final double capacity;
    private final double refillRatePerSecond;

    private final ConcurrentHashMap<String, Bucket> buckets;

    buckets = new ConcurrentHashMap<>();
    

    private class Bucket{
        double tokens;
        long lastRefillNanos;

        Bucket() {
            this.tokens = capacity;
            this.lastRefillNanos = System.nanoTime();
        }

        synchronized boolean tryConsume() {
            refill();
            if (tokens >= 1) {
                tokens -= 1;
                return true;
            }
            return false;
        }

        private void refill() {
            long now = System.nanoTime();

            long elapsedNanos = now - lastRefillNanos;

            if(elapsedNanos <= 0){
                return;
            }

            double elapsedSeconds = elapsedNanos / 1_000_000_000.0;
            double tokensToAdd = elapsedSeconds * refillRatePerSecond;
            tokens = Math.min(capacity, tokens + tokensToAdd);
            lastRefillNanos = now;
        }



    }

    public TokenBucketRateLimiter(double capacity, double refillRatePerSecond){

        if( capacity <= 0 || refillRatePerSecond<=0){
            throw new IllegalArgumentException("Capacity and refill rate must be positive.");
        }
        this.capacity = capacity;
        this.refillRatePerSecond = refillRatePerSecond;
    }

    public boolean allow(String clientID){
        Bucket bucket = buckets.computeIfAbsent(clientID, id-> new Bucket());
        return bucket.tryConsume();
    }





}