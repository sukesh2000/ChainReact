const u = await fetch(`http://user-service/users/${id}`).then(r => r.json());
render(u.name);
const o = await fetch(`http://order-service/orders/${oid}`).then(r => r.json());
charge(o.total); // assumes rupees
