import * as React from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "@/lib/auth/session";
import { PortalClientShell } from "./portal-client-shell";

export default async function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession();

  if (!session) {
    redirect("/login");
  }

  return (
    <PortalClientShell session={session}>
      {children}
    </PortalClientShell>
  );
}
