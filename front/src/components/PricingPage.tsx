import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Sparkles } from "@/components/ui/sparkles";
import { VerticalCutReveal } from "@/components/ui/vertical-cut-reveal";
import { cn } from "@/lib/utils";
import NumberFlow from "@number-flow/react";
import { motion } from "framer-motion";
import { ArrowLeft, Check } from "lucide-react";
import { useState } from "react";

// Monthly subscription plans
const subscriptionPlans = [
    {
        name: "Starter",
        tier: "S",
        description:
            "Perfect for individuals getting started with podcast summaries",
        price: 2.0,
        minutes: 240,
        buttonText: "Subscribe",
        buttonVariant: "outline" as const,
        features: [
            "240 minutes per month",
            "Auto-renew monthly",
            "1 month rollover",
            "Single LLM model",
            "Email support",
        ],
    },
    {
        name: "Medium",
        tier: "M",
        description: "Best for regular podcast listeners who want more flexibility",
        price: 5.0,
        minutes: 840,
        buttonText: "Subscribe",
        buttonVariant: "default" as const,
        popular: true,
        features: [
            "840 minutes per month",
            "Auto-renew monthly",
            "1 month rollover",
            "Single LLM model",
            "Priority email support",
        ],
    },
    {
        name: "Large",
        tier: "L",
        description:
            "For power users and heavy podcast consumers needing maximum capacity",
        price: 10.0,
        minutes: 1980,
        buttonText: "Subscribe",
        buttonVariant: "outline" as const,
        features: [
            "1,980 minutes per month",
            "Auto-renew monthly",
            "1 month rollover",
            "Single LLM model",
            "Premium support",
        ],
    },
];

// One-time minute packs
const minutePacks = [
    {
        name: "Mini",
        description: "Quick boost for occasional needs",
        price: 1.5,
        minutes: 100,
        pricePerMinute: 0.015,
        buttonText: "Buy Pack",
        buttonVariant: "outline" as const,
        features: [
            "100 minutes",
            "One-time purchase",
            "6 months validity",
            "No rollover",
            "Flexible usage",
        ],
    },
    {
        name: "Standard",
        description: "Great value for regular one-time needs",
        price: 3.0,
        minutes: 300,
        pricePerMinute: 0.01,
        buttonText: "Buy Pack",
        buttonVariant: "default" as const,
        popular: true,
        features: [
            "300 minutes",
            "One-time purchase",
            "6 months validity",
            "No rollover",
            "Flexible usage",
        ],
    },
    {
        name: "Plus",
        description: "Extended capacity for intensive periods",
        price: 6.0,
        minutes: 600,
        pricePerMinute: 0.01,
        buttonText: "Buy Pack",
        buttonVariant: "outline" as const,
        features: [
            "600 minutes",
            "One-time purchase",
            "6 months validity",
            "No rollover",
            "Flexible usage",
        ],
    },
    {
        name: "Max",
        description: "Maximum capacity for heavy usage bursts",
        price: 10.0,
        minutes: 1200,
        pricePerMinute: 0.0083,
        buttonText: "Buy Pack",
        buttonVariant: "outline" as const,
        features: [
            "1,200 minutes",
            "One-time purchase",
            "6 months validity",
            "Best value",
            "Flexible usage",
        ],
    },
];

const PricingSwitch = ({ onSwitch }: { onSwitch: (value: string) => void }) => {
    const [selected, setSelected] = useState("0");

    const handleSwitch = (value: string) => {
        setSelected(value);
        onSwitch(value);
    };

    return (
        <div className="flex justify-center">
            <div className="relative z-10 mx-auto flex w-fit rounded-full bg-white border-2 border-gray-200 p-1 shadow-sm">
                <button
                    onClick={() => handleSwitch("0")}
                    className={cn(
                        "relative z-10 w-fit h-10 rounded-full sm:px-6 px-3 sm:py-2 py-1 font-medium transition-colors",
                        selected === "0" ? "text-white" : "text-gray-600"
                    )}
                >
                    {selected === "0" && (
                        <motion.span
                            layoutId={"switch"}
                            className="absolute top-0 left-0 h-10 w-full rounded-full shadow-md shadow-blue-300 bg-gradient-to-t from-blue-500 to-blue-600"
                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        />
                    )}
                    <span className="relative">Plans</span>
                </button>

                <button
                    onClick={() => handleSwitch("1")}
                    className={cn(
                        "relative z-10 w-fit h-10 flex-shrink-0 rounded-full sm:px-6 px-3 sm:py-2 py-1 font-medium transition-colors",
                        selected === "1" ? "text-white" : "text-gray-600"
                    )}
                >
                    {selected === "1" && (
                        <motion.span
                            layoutId={"switch"}
                            className="absolute top-0 left-0 h-10 w-full rounded-full shadow-md shadow-purple-300 bg-gradient-to-t from-purple-500 to-purple-600"
                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                        />
                    )}
                    <span className="relative flex items-center gap-2">Packs</span>
                </button>
            </div>
        </div>
    );
};

interface PricingPageProps {
    onBack: () => void;
}

export default function PricingPage({ onBack }: PricingPageProps) {
    const [showPacks, setShowPacks] = useState(false);

    const togglePricingType = (value: string) =>
        setShowPacks(Number.parseInt(value) === 1);

    const currentPlans = showPacks ? minutePacks : subscriptionPlans;

    return (
        <div className="min-h-screen mx-auto relative bg-gradient-to-br from-blue-50 via-white to-purple-50 overflow-x-hidden">
            {/* Background effects */}
            <div className="absolute top-0 h-96 w-screen overflow-hidden opacity-20">
                <div className="absolute bottom-0 left-0 right-0 top-0 bg-[linear-gradient(to_right,#4f46e520_1px,transparent_1px),linear-gradient(to_bottom,#4f46e520_1px,transparent_1px)] bg-[size:70px_80px]"></div>
                <Sparkles
                    density={400}
                    direction="bottom"
                    speed={0.5}
                    color="#8b5cf6"
                    className="absolute inset-x-0 bottom-0 h-full w-full"
                />
            </div>

            {/* Gradient orbs */}
            <div
                className="absolute top-0 left-[10%] right-[10%] w-[80%] h-full z-0 opacity-20"
                style={{
                    backgroundImage: `radial-gradient(circle at center, #3b82f6 0%, transparent 70%)`,
                    mixBlendMode: "normal",
                }}
            />

            {/* Back button */}
            <button
                onClick={onBack}
                className="absolute top-8 left-8 z-50 flex items-center gap-2 px-4 py-2 text-gray-700 hover:text-blue-600 transition-colors"
            >
                <ArrowLeft size={20} />
                <span>Back</span>
            </button>

            {/* Main content */}
            <article className="text-center mb-6 pt-32 max-w-3xl mx-auto space-y-6 relative z-50 px-4">
                <h1 className="text-4xl md:text-5xl font-bold text-gray-900">
                    <VerticalCutReveal
                        splitBy="words"
                        staggerDuration={0.15}
                        staggerFrom="first"
                        reverse={true}
                        containerClassName="justify-center"
                        transition={{
                            type: "spring",
                            stiffness: 250,
                            damping: 40,
                            delay: 0,
                        }}
                    >
                        Choose the Perfect Plan for You
                    </VerticalCutReveal>
                </h1>

                <p className="text-xl text-gray-600">
                    Flexible pricing for podcast enthusiasts. Subscribe monthly or buy
                    minute packs as needed.
                </p>

                <div className="pt-4">
                    <PricingSwitch onSwitch={togglePricingType} />
                </div>
            </article>

            {/* Pricing cards */}
            <div className={`grid md:grid-cols-2 ${showPacks ? 'lg:grid-cols-4' : 'lg:grid-cols-3'} max-w-7xl gap-6 py-12 mx-auto px-4 relative z-10`}>
                {currentPlans.map((plan) => (
                    <motion.div
                        key={plan.name}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                    >
                        <Card
                            className={`relative border-2 h-full ${plan.popular
                                ? "bg-white border-blue-300 shadow-[0px_0px_40px_0px_rgba(59,130,246,0.3)] scale-105 z-20"
                                : "bg-white border-gray-200 shadow-md z-10"
                                }`}
                        >
                            {plan.popular && (
                                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 bg-gradient-to-r from-blue-500 to-purple-500 text-white px-4 py-1 rounded-full text-sm font-semibold shadow-md">
                                    Most Popular
                                </div>
                            )}

                            <CardHeader className="text-left">
                                <div className="flex justify-between items-start">
                                    <h3 className="text-2xl font-bold mb-2 text-gray-900">{plan.name}</h3>
                                </div>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-4xl font-bold text-gray-900">
                                        €
                                        <NumberFlow
                                            value={plan.price}
                                            format={{ minimumFractionDigits: 2 }}
                                            className="text-4xl font-bold"
                                        />
                                    </span>
                                    <span className="text-gray-600">
                                        {showPacks ? "" : "/month"}
                                    </span>
                                </div>
                                <p className="text-sm text-gray-600 mt-2">{plan.description}</p>
                                <p className="text-lg font-semibold text-blue-600 mt-1">
                                    {plan.minutes} minutes
                                </p>
                            </CardHeader>

                            <CardContent className="pt-0">
                                <button
                                    className={cn(
                                        "w-full mb-6 p-3 text-base rounded-xl font-semibold transition-all",
                                        plan.popular
                                            ? "bg-gradient-to-t from-blue-600 to-blue-500 shadow-lg shadow-blue-200 border border-blue-400 text-white hover:shadow-xl hover:shadow-blue-300"
                                            : "bg-gradient-to-t from-gray-100 to-gray-50 shadow-md border border-gray-300 text-gray-700 hover:bg-gray-100 hover:shadow-lg"
                                    )}
                                >
                                    {plan.buttonText}
                                </button>

                                <div className="space-y-3 pt-4 border-t border-gray-200">
                                    <h4 className="font-semibold text-sm mb-3 text-gray-700">
                                        What's included:
                                    </h4>
                                    <ul className="space-y-2">
                                        {plan.features.map((feature, featureIndex) => (
                                            <li
                                                key={featureIndex}
                                                className="flex items-start gap-2"
                                            >
                                                <Check
                                                    size={16}
                                                    className="text-green-500 mt-0.5 flex-shrink-0"
                                                />
                                                <span className="text-sm text-gray-600">{feature}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                ))}
            </div>

            {/* Footer info */}
            <div className="max-w-4xl mx-auto px-4 pb-16 text-center relative z-10">
                <p className="text-gray-600 text-sm">
                    {showPacks
                        ? "All packs are valid for 6 months from purchase. Minutes do not rollover."
                        : "Subscriptions auto-renew monthly. Unused minutes rollover for 1 month."}
                </p>
            </div>
        </div>
    );
}
