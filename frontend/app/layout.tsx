import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Observatorio Municipal CR",
  description: "Transparencia y monitoreo de datos de las 84 municipalidades de Costa Rica",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className={`${GeistSans.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900 font-sans antialiased">
        <NextIntlClientProvider messages={messages}>
          <Navbar />
          <main className="flex-1">
            {children}
          </main>
          <footer className="border-t border-slate-200 bg-white py-6 mt-16">
            <div className="container mx-auto px-4 max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-slate-500">
              <span>© 2026 Observatorio Municipal de Costa Rica</span>
              <span>Datos públicos · 84 municipalidades · Actualización continua</span>
            </div>
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
