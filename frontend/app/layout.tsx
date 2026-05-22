import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";
import Navbar from "@/components/Navbar";

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
          <footer className="border-t border-slate-200 bg-white mt-16">
            <div className="container mx-auto px-4 max-w-7xl py-8 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-md bg-blue-900 flex items-center justify-center shrink-0">
                  <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-white" stroke="currentColor" strokeWidth="1.8">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0 0 12 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75Z" />
                  </svg>
                </div>
                <span className="text-sm text-slate-600 font-medium">Observatorio Municipal de Costa Rica</span>
              </div>
              <div className="flex items-center gap-6 text-xs text-slate-400">
                <span>84 municipalidades</span>
                <span className="w-1 h-1 rounded-full bg-slate-300" />
                <span>Datos públicos</span>
                <span className="w-1 h-1 rounded-full bg-slate-300" />
                <span>© 2026</span>
              </div>
            </div>
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
