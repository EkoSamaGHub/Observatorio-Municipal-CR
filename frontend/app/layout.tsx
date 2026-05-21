import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Observatorio Municipal CR",
  description: "Monitoreo de transparencia de las 84 municipalidades de Costa Rica",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={`${GeistSans.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-gray-50 text-gray-900 font-sans">
        <NextIntlClientProvider messages={messages}>
          <Navbar />
          <main className="flex-1 container mx-auto px-4 py-8 max-w-7xl">
            {children}
          </main>
          <footer className="border-t border-gray-200 py-4 text-center text-sm text-gray-500">
            Observatorio Municipal CR — Datos públicos de las 84 municipalidades
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
