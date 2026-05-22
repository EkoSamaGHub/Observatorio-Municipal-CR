"use client";

import { useState } from "react";

const COLORS = [
  "bg-blue-700", "bg-red-700", "bg-green-700", "bg-purple-700",
  "bg-orange-600", "bg-teal-700", "bg-rose-700", "bg-indigo-700",
];

function colorFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return COLORS[h % COLORS.length];
}

interface Props {
  src: string;
  initial: string;
  seed: string;
  size?: number;
}

export default function FaviconImage({ src, initial, seed, size = 32 }: Props) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div className={`w-full h-full flex items-center justify-center rounded-lg ${colorFor(seed)}`}>
        <span className="text-white font-bold text-base select-none">{initial}</span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className="object-contain w-full h-full"
    />
  );
}
