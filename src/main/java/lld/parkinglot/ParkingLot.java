package lld.parkinglot;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public final class ParkingLot {
    private final List<ParkingSpot> spots;
    private final Map<String, Ticket> activeTickets = new LinkedHashMap<>();

    public ParkingLot(List<ParkingSpot> spots) {
        this.spots = new ArrayList<>(spots);
    }

    public Optional<Ticket> park(Vehicle vehicle) {
        for (ParkingSpot spot : spots) {
            if (spot.canFit(vehicle)) {
                spot.park(vehicle);
                Ticket ticket = Ticket.issue(spot.id(), vehicle);
                activeTickets.put(ticket.id(), ticket);
                return Optional.of(ticket);
            }
        }
        return Optional.empty();
    }

    public Vehicle leave(String ticketId) {
        Ticket ticket = activeTickets.remove(ticketId);
        if (ticket == null) {
            throw new IllegalArgumentException("Unknown ticket: " + ticketId);
        }

        ParkingSpot spot = spots.stream()
                .filter(candidate -> candidate.id().equals(ticket.spotId()))
                .findFirst()
                .orElseThrow();

        return spot.leave();
    }

    public long availableSpots(VehicleType type) {
        return spots.stream()
                .filter(ParkingSpot::isAvailable)
                .filter(spot -> spot.canFit(new Vehicle("availability-check", type)))
                .count();
    }
}

