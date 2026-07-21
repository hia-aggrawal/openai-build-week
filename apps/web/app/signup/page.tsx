import { SiteHeader } from "@/components/SiteHeader";
import { AuthForm } from "@/features/auth/components/AuthForm";

export default function SignupPage() {
  return (
    <main>
      <SiteHeader />
      <AuthForm mode="signup" />
    </main>
  );
}
