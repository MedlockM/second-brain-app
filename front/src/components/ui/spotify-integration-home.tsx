"use client";
import React, { useState, useEffect } from "react";

export default function SpotifyIntegrationHome() {
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const updateSize = () =>
      setSize({ width: window.innerWidth, height: window.innerHeight });
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Calculate icon size based on screen width
  const iconSize = size.width < 480 ? 120 : size.width < 768 ? 160 : 200;

  return (
    <section className="py-12 relative min-h-screen w-full overflow-hidden">
      {/* Semi-circle glow background */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ zIndex: 0 }}
      >
        {/* Brand subtle halo (full-viewport rectangle) */}
        <div
          className="
            absolute inset-0
            bg-[radial-gradient(ellipse_at_center,rgba(37,99,235,0.12),rgba(147,51,234,0.12)_40%,transparent_70%)]
            bg-no-repeat
            blur-[120px]
          "
        />
        {/* Spotify halo (full-viewport rectangle) */}
        <div
          className="
            absolute inset-0
            bg-[radial-gradient(ellipse_at_center,rgba(30,215,96,0.25),rgba(30,215,96,0.15)_40%,transparent_70%)]
            bg-no-repeat
            blur-[120px]
          "
        />
      </div>

      <div
        className="relative flex flex-col items-center text-center max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"
        style={{ zIndex: 10 }}
      >
        <h1 className="my-6 text-5xl md:text-6xl lg:text-7xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600">Integrations</h1>
        <p className="mb-12 max-w-2xl text-gray-600 dark:text-gray-300 text-xl md:text-2xl px-4">
          Link your Spotify account to automatically receive quizzes and
          summaries of the podcast episodes you listen to
        </p>

        <div
          className="relative flex items-center justify-center"
          style={{ minHeight: "400px" }}
        >
          {/* Large centered Spotify icon */}
          <div
            className="absolute flex flex-col items-center group cursor-pointer"
            style={{
              left: "50%",
              top: "50%",
              transform: "translate(-50%, -50%)",
              zIndex: 20,
            }}
          >
            <div className="transition-transform hover:scale-110 duration-300">
              <svg
                width={iconSize}
                height={iconSize}
                viewBox="0 0 24 24"
                fill="currentColor"
                className="text-green-500"
                style={{ minWidth: iconSize, minHeight: iconSize }}
              >
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
              </svg>
            </div>

            {/* Tooltip */}
            <div className="absolute top-[calc(100%+16px)] hidden group-hover:block w-48 rounded-lg bg-black px-4 py-2 text-xs text-white shadow-lg text-center">
              Connect Spotify
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-black"></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
