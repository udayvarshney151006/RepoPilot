import { AskRepo } from "@/components/ask-repo";
export default async function AskPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <AskRepo id={(await params).id} />;
}
