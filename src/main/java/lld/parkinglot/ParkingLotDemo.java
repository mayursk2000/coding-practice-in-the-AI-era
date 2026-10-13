package lld.parkinglot;

import java.util.List;

public final class ParkingLotDemo {
    private ParkingLotDemo() {
    }

    public static void main(String[] args) {
        ParkingLot lot = new ParkingLot(List.of(
                new ParkingSpot("C1", VehicleType.CAR),
                new ParkingSpot("C2", VehicleType.CAR),
                new ParkingSpot("M1", VehicleType.MOTORCYCLE)
        ));

        Vehicle car = new Vehicle("ABC-123", VehicleType.CAR);
        Ticket ticket = lot.park(car).orElseThrow();

        System.out.println("Parked " + car.licensePlate() + " in spot " + ticket.spotId());
        System.out.println("Available car spots: " + lot.availableSpots(VehicleType.CAR));

        Vehicle returned = lot.leave(ticket.id());
        System.out.println("Returned " + returned.licensePlate());
    }
}

