package lld.parkinglot;

public record Vehicle(String licensePlate, VehicleType type) {
    public Vehicle {
        if (licensePlate == null || licensePlate.isBlank()) {
            throw new IllegalArgumentException("licensePlate is required");
        }
        if (type == null) {
            throw new IllegalArgumentException("type is required");
        }
    }
}

