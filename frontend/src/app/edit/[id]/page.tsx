import { redirect } from "next/navigation";

export default function OldEditRedirect({ params }: { params: { id: string } }) {
  redirect(`/strategy-builder/edit/${params.id}`);
}
