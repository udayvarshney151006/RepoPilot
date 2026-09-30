export function formatPrice(amount) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount);
}

export function cartItemCount(items) {
  return items.reduce((total, item) => total + (item.quantity ?? 1), 0);
}
