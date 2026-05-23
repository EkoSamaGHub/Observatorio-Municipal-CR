import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: {
    default: "Observatorio Municipal CR",
    template: "%s · Observatorio Municipal CR",
  },
  description: "Transparencia, documentos y monitoreo de las 84 municipalidades de Costa Rica.",
  keywords: ["Costa Rica", "municipalidades", "transparencia", "datos públicos"],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={`${GeistSans.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-slate-100 text-slate-900 font-sans antialiased">
        <NextIntlClientProvider messages={messages}>
          <Navbar />
          <main className="flex-1 container mx-auto px-4 max-w-7xl py-8">
            {children}
          </main>
          <Footer />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
