import "./globals.css";

export const metadata = {
  title: "Career-Orbit | Agentic Job Portal",
  description: "Your autonomous AI-powered job search and application engine.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
