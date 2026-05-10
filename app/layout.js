import "./globals.css";

export const metadata = {
  title: "Job Hunt Hub | Management System",
  description: "Track and manage your automated job applications with ease.",
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
