import { useQuery } from "@tanstack/react-query";

export interface MedicalNewsCard {
  id: string;
  headline: string;
  source: string;
  summary: string;
  href: string;
}

const mockNews: MedicalNewsCard[] = [
  {
    id: "news-1",
    headline: "AI model flags early-stage sepsis in ER triage workflows",
    source: "HealthTech Daily",
    summary: "Multi-center trial reports a measurable reduction in delayed interventions when AI alerts are embedded at triage.",
    href: "#",
  },
  {
    id: "news-2",
    headline: "Remote cardiac monitoring expands into rural community clinics",
    source: "Clinical Wire",
    summary: "Low-cost wearables paired with care coordination teams reduced hospital readmissions by 11%.",
    href: "#",
  },
  {
    id: "news-3",
    headline: "FHIR-based data exchange standardizes medication histories",
    source: "Interop Journal",
    summary: "Regional providers reported faster medication reconciliation and fewer duplicate prescriptions.",
    href: "#",
  },
  {
    id: "news-4",
    headline: "New guideline promotes proactive preventive screening reminders",
    source: "Public Health Review",
    summary: "Automated reminder systems improved annual screening adherence in primary care cohorts.",
    href: "#",
  },
  {
    id: "news-5",
    headline: "Digital therapeutic pilot shows improved diabetes outcomes",
    source: "Med Outcomes",
    summary: "Patients using app-guided daily coaching recorded stronger HbA1c improvements over 6 months.",
    href: "#",
  },
];

async function fetchMedicalNewsFromAgent(): Promise<MedicalNewsCard[]> {
  await new Promise((resolve) => setTimeout(resolve, 650));
  return mockNews;
}

export function useMedicalNewsAgent() {
  return useQuery({
    queryKey: ["medical-news-agent"],
    queryFn: fetchMedicalNewsFromAgent,
    staleTime: 1000 * 60 * 15,
  });
}
