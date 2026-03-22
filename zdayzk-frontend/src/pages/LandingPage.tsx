import React from "react";
import { Hero } from "../components/landing/Hero";
import { HowItWorks } from "../components/landing/HowItWorks";
import { TrustSignals } from "../components/landing/TrustSignals";
import { Footer } from "../components/landing/Footer";

export function LandingPage() {
  return (
    <div className="min-h-screen">
      <Hero />
      <HowItWorks />
      <TrustSignals />
      <Footer />
    </div>
  );
}
