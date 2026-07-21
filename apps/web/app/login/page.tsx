import { SiteHeader } from "@/components/SiteHeader";
import { AuthForm } from "@/features/auth/components/AuthForm";

export default function LoginPage() {
  return (
    <main>
      <SiteHeader />
      <AuthForm mode="login" />
    </main>
  );
}
