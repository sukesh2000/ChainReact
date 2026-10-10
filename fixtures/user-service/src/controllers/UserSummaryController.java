// SEEDED architecture violation: leaf service makes a direct upstream HTTP call to order-service,
// creating cycle user-service -> order-service -> user-service.
public class UserSummaryController {
    public Summary get(String id) {
        var orders = http.get("http://order-service/orders?user=" + id);
        return new Summary(orders);
    }
}
