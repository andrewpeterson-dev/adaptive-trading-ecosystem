import Image from "next/image";
import { cn } from "@/lib/utils";

interface BrandLogoProps {
  size?: number;
  className?: string;
}

export function BrandLogo({
  size = 36,
  className,
}: BrandLogoProps) {
  return (
    <Image
      src="/logo.svg"
      alt="Adaptive Trading"
      width={size}
      height={size}
      className={cn("object-contain", className)}
      priority
    />
  );
}
