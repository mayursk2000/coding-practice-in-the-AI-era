package lld.parkinglot;

import java.util.Optional;

public final class ParkingSpot {
    private final String id;
    private final VehicleType supportedType;
    private Vehicle parkedVehicle;

    public ParkingSpot(String id, VehicleType supportedType) {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("id is required");
        }
        if (supportedType == null) {
            throw new IllegalArgumentException("supportedType is required");
        }
        this.id = id;
        this.supportedType = supportedType;
    }

    public String id() {
        return id;
    }

    public boolean isAvailable() {
        return parkedVehicle == null;
    }

    public boolean canFit(Vehicle vehicle) {
        return isAvailable() && supportedType == vehicle.type();
    }

    public Optional<Vehicle> parkedVehicle() {
        return Optional.ofNullable(parkedVehicle);
    }

    void park(Vehicle vehicle) {
        if (!canFit(vehicle)) {
            throw new IllegalStateException("Vehicle cannot park in spot " + id);
        }
        parkedVehicle = vehicle;
    }

    Vehicle leave() {
        if (parkedVehicle == null) {
            throw new IllegalStateException("Spot " + id + " is already empty");
        }
        Vehicle vehicle = parkedVehicle;
        parkedVehicle = null;
        return vehicle;
    }
}

