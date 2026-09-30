import { Agent } from "@/components/agent";
export default async function AgentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <Agent id={(await params).id} />;
}
