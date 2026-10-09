import { CityPicker } from "@/components/CityPicker";
import { Problem } from "@/components/Problem";
import { Sprouts } from "@/components/Sprouts";
import { Trail } from "@/components/Trail";
import { getCities, statusOf } from "@/lib/api";
import type { CitySummary } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "Choose your city" };

export default async function HomePage() {
  let cities: CitySummary[];
  try {
    cities = await getCities();
  } catch (error) {
    return <Problem status={statusOf(error)} />;
  }
  return (
    <>
      <Trail items={[{ label: "Cities" }]} />
      <CityPicker cities={cities} art={<Sprouts />} />
    </>
  );
}
