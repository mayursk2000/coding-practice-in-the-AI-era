package lld.parkinglot;

import java.time.Instant;
import java.util.UUID;

public record Ticket(String id, String spotId, Vehicle vehicle, Instant issuedAt) {
    public static Ticket issue(String spotId, Vehicle vehicle) {
        return new Ticket(UUID.randomUUID().toString(), spotId, vehicle, Instant.now());
    }
}

