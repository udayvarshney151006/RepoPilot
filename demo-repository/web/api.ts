export interface CartItem {
  price: number;
  quantity?: number;
}

export async function submitCheckout(items: CartItem[], token: string) {
  const response = await fetch("/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ items }),
  });
  if (!response.ok) throw new Error(`Checkout failed: ${response.status}`);
  return response.json();
}
