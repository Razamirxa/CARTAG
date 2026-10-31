import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { Logo } from "../components/layouts";
import { Swatch, TAG_COLOURS, TagArt } from "../components/TagArt";
import { Toggle, linkButton } from "../components/ui";
import { api, type Product, type ProductColour } from "../lib/api";
import { rs } from "../lib/format";

const COLOURS: ProductColour[] = ["BLACK", "IVORY", "BURGUNDY", "GLACIER"];

/** A small copy of the real scan page, so people see exactly what a stranger gets. */
function PhonePreview({ emergency }: { emergency: boolean }) {
  return (
    <div
      className="mx-auto w-[17.5rem] rounded-[2.5rem] border-[10px] p-3.5"
      style={{ borderColor: "#0A0A0A", background: "var(--c-bg)" }}
      aria-hidden="true"
    >
      <div className="flex items-center justify-between px-1 pb-3 pt-1">
        <Logo className="scale-90 origin-left" />
        <span className="rounded-full border border-line px-2 py-0.5 text-[0.7rem] font-semibold text-brand">اردو</span>
      </div>
      <div className="rounded-2xl border border-line bg-surface p-4">
        <p className="heading text-lg">Contact the owner</p>
        <p className="mt-0.5 text-[0.8rem] leading-snug text-muted">The owner of this CARTAG can be reached with the buttons below.</p>
        <p className="mt-3 border-t border-line pt-3 text-xl font-extrabold">Ali Raza</p>
        <div className="mt-3 space-y-2">
          <span className="flex h-11 items-center justify-center rounded-full text-sm font-bold" style={{ background: "#0A0A0A", color: "#F5F1E8" }}>
            Call Owner
          </span>
          <span className="flex h-11 items-center justify-center rounded-full text-sm font-bold text-white" style={{ background: "#1A8F4A" }}>
            WhatsApp Owner
          </span>
        </div>
      </div>
      {emergency && (
        <div className="mt-2.5 rounded-2xl border border-line bg-surface p-4">
          <p className="text-sm font-extrabold" style={{ color: "#B3261E" }}>
            Emergency information
          </p>
          <p className="mt-2 flex justify-between text-sm">
            <span className="text-muted">Blood group</span>
            <span className="font-bold">O+</span>
          </p>
          <p className="mt-1 flex justify-between text-sm">
            <span className="text-muted">Contact</span>
            <span className="font-bold">Sara (wife)</span>
          </p>
          <span className="mt-3 flex h-10 items-center justify-center rounded-full text-sm font-bold text-white" style={{ background: "#B3261E" }}>
            Call emergency contact
          </span>
        </div>
      )}
    </div>
  );
}

const steps = [
  { title: "Get a tag", body: "Order one here, or buy one from a seller." },
  { title: "Scan and sign in", body: "Scan the QR code on the tag with your phone camera, then sign in or create an account." },
  { title: "Confirm your mobile", body: "We text you a six-digit code to make sure the tag is yours." },
  { title: "Add your card and turn it on", body: "Your name, and if you want it, Emergency Mode. Then the tag works." },
];

const faqs = [
  {
    q: "Does the person who scans need an app?",
    a: "No. They scan with the phone camera and the page opens in the browser.",
  },
  {
    q: "Can they see my phone number?",
    a: "It is not written on the page. The Call and WhatsApp buttons use it, as any phone link does.",
  },
  {
    q: "What if I lose my tag or it gets damaged?",
    a: "Contact us and we retire it. A replacement tag has a new QR code, and the old code can never be used again.",
  },
  {
    q: "Can I give my tag to someone else?",
    a: "No. A tag stays with the account that turned it on. If you sell your car, turn the tag off and buy a new one for the next vehicle.",
  },
  {
    q: "How do I stop people reaching me?",
    a: "Turn the tag off in your account. A scan then shows that the tag is off, and nothing about you.",
  },
];

export default function Home() {
  const [colour, setColour] = useState<ProductColour>("BURGUNDY");
  const [emergency, setEmergency] = useState(false);
  const products = useQuery({
    queryKey: ["shop", "products"],
    queryFn: async () => (await api<{ products: Product[] }>("/api/shop/products")).products,
  });
  const from = products.data && products.data.length > 0 ? Math.min(...products.data.map((p) => p.price)) : null;

  return (
    <div className="space-y-24 sm:space-y-32">
      {/* The first thing anyone sees is the product itself, in the colour they pick. */}
      <section className="grid items-center gap-10 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <h1 className="display text-[clamp(2.4rem,6.2vw,4.6rem)]">
            Anyone can reach you. Your number stays off the page.
          </h1>
          <p className="mt-6 text-lg text-muted">
            CARTAG is a QR tag for your car or bike. Whoever scans it can call you or message you on WhatsApp. Your number sits
            behind the buttons and is never printed on the page.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/shop" className={linkButton("primary", "min-h-12 px-7 text-base")}>
              Shop CARTAG
            </Link>
            <Link to="/account" className={linkButton("secondary", "min-h-12 px-7 text-base")}>
              I already have a tag
            </Link>
          </div>
          {from !== null && <p className="mt-4 text-sm text-muted">Tags start at {rs(from)}.</p>}
        </div>

        <div className="relative rounded-[2.25rem] bg-subtle px-6 pb-6 pt-10">
          <div className="absolute inset-x-0 top-0 mx-auto h-16 w-px bg-line" aria-hidden="true" />
          <TagArt
            colour={colour}
            title={`A ${TAG_COLOURS[colour].name} CARTAG tag`}
            className="mx-auto w-[min(15rem,62vw)] origin-top -rotate-3 transition-transform duration-500 hover:rotate-0"
          />
          <div className="mt-4 flex items-center justify-center gap-1" role="group" aria-label="Tag colour">
            {COLOURS.map((c) => (
              <Swatch key={c} colour={c} selected={c === colour} onClick={() => setColour(c)} />
            ))}
          </div>
          <p className="text-center text-sm font-semibold" aria-live="polite">
            {TAG_COLOURS[colour].name}
            {(colour === "BURGUNDY" || colour === "GLACIER") && <span className="font-normal text-muted"> (premium colour)</span>}
          </p>
        </div>
      </section>

      <section className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <h2 className="heading text-3xl sm:text-4xl">What the person who scans sees</h2>
          <p className="mt-4 text-muted">A name and two buttons. That is all they need to get in touch, and all they get.</p>
          <ul className="mt-6 space-y-4">
            <li>
              <p className="font-semibold">Your number stays private</p>
              <p className="text-muted">The buttons use it. The page never prints it.</p>
            </li>
            <li>
              <p className="font-semibold">Emergency Mode is off until you turn it on</p>
              <p className="text-muted">When on, the page also shows your blood group and one emergency contact.</p>
            </li>
            <li>
              <p className="font-semibold">English and Urdu, in any browser</p>
              <p className="text-muted">There is nothing to install.</p>
            </li>
          </ul>
          <div className="mt-6 max-w-sm rounded-2xl border border-line bg-surface px-4 py-1">
            <Toggle label="Show Emergency Mode in the preview" checked={emergency} onChange={setEmergency} />
          </div>
        </div>
        <PhonePreview emergency={emergency} />
      </section>

      <section>
        <h2 className="heading text-3xl sm:text-4xl">How you start</h2>
        <ol className="mt-8 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => (
            <li key={step.title} className="border-t-2 border-ink pt-4">
              <span className="display text-4xl text-brand tabular-nums">{index + 1}</span>
              <p className="mt-3 text-lg font-semibold">{step.title}</p>
              <p className="mt-1 text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-[2.25rem] bg-subtle px-6 py-10 sm:px-12">
        <div className="grid items-center gap-8 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <h2 className="heading text-3xl sm:text-4xl">Four colours, three sizes</h2>
            <p className="mt-4 text-muted">Black and Ivory are the standard colours. Burgundy and Glacier cost a little more.</p>
            <Link to="/shop" className={linkButton("primary", "mt-6")}>
              See sizes and prices
            </Link>
          </div>
          <div className="grid grid-cols-4 items-end gap-3 sm:gap-6">
            {COLOURS.map((c, index) => (
              <figure key={c} className={index % 2 ? "translate-y-3" : undefined}>
                <TagArt colour={c} title={`${TAG_COLOURS[c].name} tag`} className="w-full" shadow={false} />
                <figcaption className="mt-2 text-center text-sm font-semibold">{TAG_COLOURS[c].name}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-3xl">
        <h2 className="heading text-3xl sm:text-4xl">Questions people ask</h2>
        <div className="mt-6 divide-y divide-line border-y border-line">
          {faqs.map((item) => (
            <details key={item.q} className="group py-4">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold [&::-webkit-details-marker]:hidden">
                {item.q}
                <span aria-hidden="true" className="text-xl text-brand transition-transform group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="mt-3 text-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
