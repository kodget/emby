// Shared sample data for Emby (BMS Edition)
// Designed around Anatomy, Physiology, and Medical Biochemistry.

export type Course = {
  id: string;
  code: string;
  title: string;
  subject: "Anatomy" | "Physiology" | "Biochemistry";
  lecturer: string;
  students: number;
  progress: number;
  color: string;
  icon: string;
  description: string;
  nextClass: string;
  modules: Module[];
};

export type Module = {
  id: string;
  title: string;
  summary: string;
  materials: Material[];
  pastQuestions: number;
};

export type Material = {
  id: string;
  title: string;
  kind: "slide" | "pdf" | "note" | "video";
  pages: number;
  uploadedBy: string;
  uploadedAt: string;
  // For reader demo
  body?: ReaderBlock[];
};

export type ReaderBlock =
  | { type: "h1"; text: string }
  | { type: "h2"; text: string }
  | { type: "p"; text: string }
  | { type: "figure"; src: string; caption: string }
  | { type: "list"; items: string[] }
  | {
      type: "callout";
      variant: "clinical" | "highyield" | "mnemonic";
      title: string;
      body: string;
    }
  | { type: "slide"; src: string; pageNumber: number };

export const courses: Course[] = [
  {
    id: "anat-101",
    code: "ANAT 201",
    title: "Gross Anatomy of the Upper Limb",
    subject: "Anatomy",
    lecturer: "Dr. Adeyemi",
    students: 142,
    progress: 62,
    color: "#0d6b5e",
    icon: "Bone",
    description:
      "Osteology, myology, vasculature and innervation of the shoulder girdle, arm, forearm and hand. Includes clinical correlations for brachial plexus injuries.",
    nextClass: "Tomorrow, 8:00 AM · LT1",
    modules: [
      {
        id: "anat-101-m1",
        title: "Pectoral Region & Axilla",
        summary:
          "Boundaries of the axilla, contents, brachial plexus, axillary artery branches.",
        pastQuestions: 48,
        materials: [
          {
            id: "anat-101-m1-s1",
            title: "Axilla: Boundaries & Contents",
            kind: "slide",
            pages: 34,
            uploadedBy: "Uploader · Chioma",
            uploadedAt: "2 days ago",
            body: axillaReaderBody(),
          },
          {
            id: "anat-101-m1-s2",
            title: "Brachial Plexus Simplified",
            kind: "pdf",
            pages: 18,
            uploadedBy: "Uploader · Chioma",
            uploadedAt: "5 days ago",
          },
        ],
      },
      {
        id: "anat-101-m2",
        title: "Arm & Cubital Fossa",
        summary:
          "Compartments of the arm, flexor/extensor muscles, cubital fossa boundaries.",
        pastQuestions: 31,
        materials: [
          {
            id: "anat-101-m2-s1",
            title: "Compartments of the Arm",
            kind: "slide",
            pages: 22,
            uploadedBy: "Uploader · Chioma",
            uploadedAt: "1 week ago",
          },
        ],
      },
      {
        id: "anat-101-m3",
        title: "Forearm & Hand",
        summary:
          "Intrinsic hand muscles, carpal tunnel, median/ulnar/radial nerve distribution.",
        pastQuestions: 57,
        materials: [
          {
            id: "anat-101-m3-s1",
            title: "The Hand: Intrinsic Muscles",
            kind: "slide",
            pages: 40,
            uploadedBy: "Uploader · Chioma",
            uploadedAt: "3 days ago",
          },
        ],
      },
    ],
  },
  {
    id: "phys-201",
    code: "PHYS 211",
    title: "Cardiovascular Physiology",
    subject: "Physiology",
    lecturer: "Prof. Okonkwo",
    students: 138,
    progress: 48,
    color: "#b94a3b",
    icon: "HeartPulse",
    description:
      "Cardiac cycle, electrical activity of the heart, blood pressure regulation, and clinical correlations in heart failure.",
    nextClass: "Wednesday, 10:00 AM · Physiology Lab",
    modules: [
      {
        id: "phys-201-m1",
        title: "Cardiac Cycle & Heart Sounds",
        summary:
          "Systole, diastole, Wiggers diagram, first and second heart sounds.",
        pastQuestions: 42,
        materials: [
          {
            id: "phys-201-m1-s1",
            title: "The Wiggers Diagram Explained",
            kind: "slide",
            pages: 28,
            uploadedBy: "Uploader · Tunde",
            uploadedAt: "4 days ago",
          },
        ],
      },
      {
        id: "phys-201-m2",
        title: "ECG Interpretation Basics",
        summary: "P wave, QRS complex, T wave, and approach to a 12-lead ECG.",
        pastQuestions: 36,
        materials: [
          {
            id: "phys-201-m2-s1",
            title: "Reading a 12-lead ECG",
            kind: "slide",
            pages: 32,
            uploadedBy: "Uploader · Tunde",
            uploadedAt: "1 week ago",
          },
        ],
      },
    ],
  },
  {
    id: "bioc-101",
    code: "BIOC 221",
    title: "Carbohydrate Metabolism",
    subject: "Biochemistry",
    lecturer: "Dr. Nwachukwu",
    students: 151,
    progress: 34,
    color: "#6b7d3a",
    icon: "FlaskConical",
    description:
      "Glycolysis, TCA cycle, gluconeogenesis, glycogen metabolism, and the pentose phosphate pathway with clinical correlations.",
    nextClass: "Friday, 2:00 PM · Biochem Hall",
    modules: [
      {
        id: "bioc-101-m1",
        title: "Glycolysis",
        summary:
          "Ten-step pathway, regulation, and energy yield. Irreversible steps and their enzymes.",
        pastQuestions: 53,
        materials: [
          {
            id: "bioc-101-m1-s1",
            title: "Glycolysis: Step by Step",
            kind: "slide",
            pages: 26,
            uploadedBy: "Uploader · Amara",
            uploadedAt: "Today",
          },
        ],
      },
      {
        id: "bioc-101-m2",
        title: "TCA Cycle",
        summary: "Eight enzymatic steps, ATP yield, and clinical implications.",
        pastQuestions: 41,
        materials: [
          {
            id: "bioc-101-m2-s1",
            title: "The Citric Acid Cycle",
            kind: "slide",
            pages: 24,
            uploadedBy: "Uploader · Amara",
            uploadedAt: "6 days ago",
          },
        ],
      },
    ],
  },
  {
    id: "anat-202",
    code: "ANAT 202",
    title: "Head & Neck Anatomy",
    subject: "Anatomy",
    lecturer: "Dr. Bello",
    students: 140,
    progress: 15,
    color: "#0d6b5e",
    icon: "Brain",
    description:
      "Skull osteology, cranial nerves, triangles of the neck, and clinical correlations.",
    nextClass: "Monday, 8:00 AM · LT2",
    modules: [
      {
        id: "anat-202-m1",
        title: "Cranial Nerves Overview",
        summary:
          "All 12 cranial nerves, their origins, functions, and lesion presentations.",
        pastQuestions: 62,
        materials: [
          {
            id: "anat-202-m1-s1",
            title: "Cranial Nerves: All 12",
            kind: "slide",
            pages: 44,
            uploadedBy: "Uploader · Kelechi",
            uploadedAt: "2 days ago",
          },
        ],
      },
    ],
  },
];

function axillaReaderBody(): ReaderBlock[] {
  return [
    { type: "h1", text: "The Axilla: Boundaries and Contents" },
    {
      type: "p",
      text: "The axilla is a pyramidal space between the upper part of the thoracic wall and the arm. It serves as a passageway for neurovascular structures travelling between the neck and the upper limb. Clinically, it is a site of frequent examination in breast cancer staging, brachial plexus injury, and lymphadenopathy.",
    },
    {
      type: "callout",
      variant: "highyield",
      title: "High yield",
      body: "Know the apex, base, and four walls of the axilla in order. Examiners often ask for the contents of the medial wall (serratus anterior, long thoracic nerve).",
    },
    { type: "h2", text: "Boundaries" },
    {
      type: "p",
      text: "The axilla has an apex, a base, and four walls. It is best visualised as a truncated pyramid.",
    },
    {
      type: "list",
      items: [
        "Apex (cervico-axillary canal): bounded by the clavicle, first rib, and superior border of scapula.",
        "Base (axillary fascia): formed by skin and axillary fascia between the arm and chest wall.",
        "Anterior wall: pectoralis major and minor, subclavius.",
        "Posterior wall: subscapularis, teres major, latissimus dorsi.",
        "Medial wall: upper 4–5 ribs with their intercostal muscles and serratus anterior.",
        "Lateral wall: intertubercular groove of the humerus.",
      ],
    },
    { type: "h2", text: "Contents" },
    {
      type: "p",
      text: "The axilla contains the axillary artery and its branches, the axillary vein and its tributaries, cords and branches of the brachial plexus, axillary lymph nodes, and fat. The long thoracic nerve runs on the surface of serratus anterior and is vulnerable during mastectomy, where injury causes winging of the scapula.",
    },
    {
      type: "callout",
      variant: "clinical",
      title: "Clinical correlation",
      body: "A patient presenting with winged scapula after mastectomy most likely has damage to the long thoracic nerve (C5–C7), which supplies serratus anterior on the medial wall of the axilla.",
    },
    { type: "h2", text: "The Brachial Plexus" },
    {
      type: "p",
      text: "Formed by the ventral rami of C5–T1, the brachial plexus passes through the axilla as cords (lateral, medial, and posterior), named according to their relationship to the axillary artery. The cords give rise to the terminal branches that innervate the upper limb.",
    },
    {
      type: "callout",
      variant: "mnemonic",
      title: "Mnemonic",
      body: "Randy Travis Drinks Cold Beer: Roots, Trunks, Divisions, Cords, Branches.",
    },
  ];
}

// ---------------- Quizzes ----------------

export type MCQ = {
  id: string;
  question: string;
  options: string[];
  correct: number;
  explanation: string;
  topic: string;
};

export const quizzes: Record<
  string,
  {
    id: string;
    title: string;
    topic: string;
    durationSec: number;
    questions: MCQ[];
  }
> = {
  "axilla-mcq": {
    id: "axilla-mcq",
    title: "Axilla & Brachial Plexus",
    topic: "Upper Limb Anatomy",
    durationSec: 300,
    questions: [
      {
        id: "q1",
        question:
          "A 52-year-old woman develops winging of the scapula after a radical mastectomy. Which nerve is most likely injured?",
        options: [
          "Long thoracic nerve",
          "Thoracodorsal nerve",
          "Axillary nerve",
          "Median nerve",
        ],
        correct: 0,
        explanation:
          "The long thoracic nerve (C5–C7) innervates serratus anterior. Injury causes winging of the scapula, classically seen after axillary surgery.",
        topic: "Brachial plexus",
      },
      {
        id: "q2",
        question: "Which structure forms the lateral wall of the axilla?",
        options: [
          "Pectoralis major",
          "Serratus anterior",
          "Intertubercular groove of humerus",
          "Latissimus dorsi",
        ],
        correct: 2,
        explanation:
          "The lateral wall of the axilla is the intertubercular (bicipital) groove of the humerus. The medial wall is formed by serratus anterior.",
        topic: "Axilla boundaries",
      },
      {
        id: "q3",
        question:
          "The cords of the brachial plexus are named based on their relationship to which structure?",
        options: [
          "The clavicle",
          "The axillary artery",
          "The first rib",
          "The pectoralis minor",
        ],
        correct: 1,
        explanation:
          "The lateral, medial, and posterior cords are named by their relationship to the axillary artery.",
        topic: "Brachial plexus",
      },
      {
        id: "q4",
        question:
          "A patient cannot abduct the arm beyond 15 degrees and has loss of sensation over the regimental badge area. Which nerve is affected?",
        options: ["Radial", "Axillary", "Musculocutaneous", "Suprascapular"],
        correct: 1,
        explanation:
          "Axillary nerve injury impairs deltoid (abduction 15–90°) and teres minor, with sensory loss over the lateral shoulder (regimental badge area).",
        topic: "Brachial plexus",
      },
      {
        id: "q5",
        question:
          "The apex of the axilla is bounded anteriorly by which structure?",
        options: [
          "The first rib",
          "The clavicle",
          "The superior border of the scapula",
          "The coracoid process",
        ],
        correct: 1,
        explanation:
          "The cervico-axillary canal (apex) is bounded by the clavicle anteriorly, first rib medially, and superior border of scapula posteriorly.",
        topic: "Axilla boundaries",
      },
    ],
  },
  "glycolysis-mcq": {
    id: "glycolysis-mcq",
    title: "Glycolysis: Enzymes & Regulation",
    topic: "Carbohydrate Metabolism",
    durationSec: 240,
    questions: [
      {
        id: "q1",
        question:
          "Which enzyme catalyses the rate-limiting step of glycolysis?",
        options: [
          "Hexokinase",
          "Phosphofructokinase-1",
          "Pyruvate kinase",
          "Aldolase",
        ],
        correct: 1,
        explanation:
          "PFK-1 is the rate-limiting enzyme. It is allosterically activated by AMP and F2,6-BP, and inhibited by ATP and citrate.",
        topic: "Glycolysis regulation",
      },
      {
        id: "q2",
        question: "The net ATP yield of glycolysis per glucose molecule is:",
        options: ["1", "2", "4", "6"],
        correct: 1,
        explanation:
          "Glycolysis generates 4 ATP but consumes 2, for a net of 2 ATP per glucose. It also yields 2 NADH.",
        topic: "Glycolysis energetics",
      },
      {
        id: "q3",
        question: "Red blood cells rely on glycolysis because they lack:",
        options: ["Ribosomes", "Mitochondria", "A plasma membrane", "Nuclei"],
        correct: 1,
        explanation:
          "RBCs lack mitochondria and rely entirely on anaerobic glycolysis for ATP; pyruvate is converted to lactate to regenerate NAD+.",
        topic: "Clinical correlations",
      },
    ],
  },
  "cardiac-mcq": {
    id: "cardiac-mcq",
    title: "Cardiac Cycle Essentials",
    topic: "Cardiovascular Physiology",
    durationSec: 240,
    questions: [
      {
        id: "q1",
        question: "The first heart sound (S1) is produced by closure of:",
        options: [
          "Aortic and pulmonary valves",
          "Mitral and tricuspid valves",
          "Mitral and aortic valves",
          "Tricuspid and pulmonary valves",
        ],
        correct: 1,
        explanation:
          "S1 is produced by closure of the AV valves (mitral and tricuspid) at the start of ventricular systole.",
        topic: "Heart sounds",
      },
      {
        id: "q2",
        question:
          "During isovolumetric contraction, which of the following is TRUE?",
        options: [
          "All four valves are open",
          "Ventricular volume changes",
          "All four valves are closed",
          "Aortic valve is open",
        ],
        correct: 2,
        explanation:
          "During isovolumetric contraction, all valves are closed. The ventricles contract without volume change until pressure exceeds aortic and pulmonary pressure.",
        topic: "Cardiac cycle phases",
      },
    ],
  },
};

// ---------------- Steeplechase ----------------

export type SteeplechaseItem = {
  id: string;
  image: string;
  imageQuery: string;
  prompt: string;
  acceptedAnswers: string[];
  explanation: string;
  topic: string;
};

export const steeplechaseSets: Record<
  string,
  { id: string; title: string; durationSec: number; items: SteeplechaseItem[] }
> = {
  "upper-limb": {
    id: "upper-limb",
    title: "Upper Limb Steeplechase: Set 1",
    durationSec: 45, // per station
    items: [
      {
        id: "s1",
        image: "/placeholder.svg?height=520&width=720",
        imageQuery: "cadaveric dissection of axillary artery labeled with pin",
        prompt: "Identify the structure marked with pin A.",
        acceptedAnswers: ["axillary artery", "3rd part of axillary artery"],
        explanation:
          "The axillary artery runs from the outer border of the first rib to the lower border of teres major, divided into 3 parts by pectoralis minor.",
        topic: "Upper limb vasculature",
      },
      {
        id: "s2",
        image: "/placeholder.svg?height=520&width=720",
        imageQuery: "brachial plexus dissection with lateral cord pinned",
        prompt: "Identify the cord of the brachial plexus marked.",
        acceptedAnswers: ["lateral cord"],
        explanation:
          "The lateral cord lies lateral to the axillary artery and gives rise to the lateral pectoral nerve, musculocutaneous nerve, and the lateral root of the median nerve.",
        topic: "Brachial plexus",
      },
      {
        id: "s3",
        image: "/placeholder.svg?height=520&width=720",
        imageQuery: "dissection of serratus anterior on thoracic wall",
        prompt: "Name the muscle that forms the medial wall of the axilla.",
        acceptedAnswers: ["serratus anterior"],
        explanation:
          "Serratus anterior, innervated by the long thoracic nerve (C5–C7), forms most of the medial wall of the axilla.",
        topic: "Axilla boundaries",
      },
      {
        id: "s4",
        image: "/placeholder.svg?height=520&width=720",
        imageQuery: "hand dissection showing thenar muscles",
        prompt: "Name the muscle group indicated at the base of the thumb.",
        acceptedAnswers: ["thenar", "thenar muscles", "thenar eminence"],
        explanation:
          "The thenar eminence comprises abductor pollicis brevis, flexor pollicis brevis, and opponens pollicis, all supplied by the recurrent branch of the median nerve.",
        topic: "Hand anatomy",
      },
      {
        id: "s5",
        image: "/placeholder.svg?height=520&width=720",
        imageQuery: "cubital fossa dissection with median nerve",
        prompt:
          "Which nerve passes medial to the brachial artery in the cubital fossa?",
        acceptedAnswers: ["median nerve"],
        explanation:
          "In the cubital fossa, the median nerve lies medial to the brachial artery and its pulse. Mnemonic for contents, lateral to medial: Really Need Beer To Be At My Nicest (Radial N, Biceps T, Brachial A, Median N).",
        topic: "Cubital fossa",
      },
    ],
  },
};

// ---------------- Flashcards ----------------

export type Flashcard = {
  id: string;
  front: string;
  back: string;
  topic?: string;
  deck: string;
  due: boolean;
  easeFactor?: number;
  interval?: number;
  repetitions?: number;
  nextReview?: Date;
};

export const flashcards: Flashcard[] = [
  {
    id: "f1",
    front: "What are the boundaries of the axilla?",
    back: "Apex (cervico-axillary canal), base (axillary fascia), anterior wall (pec major/minor), posterior wall (subscapularis, teres major, lat dorsi), medial wall (serratus anterior + ribs), lateral wall (bicipital groove of humerus).",
    topic: "Axilla",
    deck: "Upper Limb",
    due: true,
  },
  {
    id: "f2",
    front: "Which nerve injury causes winging of the scapula?",
    back: "Long thoracic nerve (C5–C7), supplying serratus anterior. Classic cause: radical mastectomy.",
    topic: "Brachial plexus",
    deck: "Upper Limb",
    due: true,
  },
  {
    id: "f3",
    front: "Rate-limiting enzyme of glycolysis?",
    back: "Phosphofructokinase-1 (PFK-1). Activated by AMP, F2,6-BP. Inhibited by ATP, citrate.",
    topic: "Glycolysis",
    deck: "Biochemistry",
    due: true,
  },
  {
    id: "f4",
    front: "What produces the first heart sound (S1)?",
    back: "Closure of the mitral and tricuspid (AV) valves at the onset of ventricular systole.",
    topic: "Cardiac cycle",
    deck: "Physiology",
    due: true,
  },
  {
    id: "f5",
    front: "Net ATP yield of glycolysis?",
    back: "2 ATP and 2 NADH per glucose. (4 ATP produced, 2 consumed.)",
    topic: "Glycolysis",
    deck: "Biochemistry",
    due: false,
  },
  {
    id: "f6",
    front: "Cranial nerves mnemonic (I–XII)?",
    back: "Oh Oh Oh To Touch And Feel Very Good Velvet, AH! stands for Olfactory, Optic, Oculomotor, Trochlear, Trigeminal, Abducens, Facial, Vestibulocochlear, Glossopharyngeal, Vagus, Accessory, Hypoglossal.",
    topic: "Cranial nerves",
    deck: "Head & Neck",
    due: true,
  },
];

// ---------------- Community ----------------

export type CommunityPost = {
  id: string;
  author: string;
  authorRole: "student" | "class-rep" | "top-student";
  avatar: string;
  title: string;
  body: string;
  course: string;
  tags: string[];
  upvotes: number;
  answers: number;
  time: string;
};

export const community: CommunityPost[] = [
  {
    id: "p1",
    author: "Ifeoma U.",
    authorRole: "student",
    avatar: "/placeholder.svg?height=64&width=64",
    title:
      "Can someone explain the difference between the 3 parts of the axillary artery?",
    body: "I keep mixing up the branches. Is there a simple way to remember which branches come from which part?",
    course: "ANAT 201",
    tags: ["axilla", "mnemonic"],
    upvotes: 24,
    answers: 7,
    time: "3h ago",
  },
  {
    id: "p2",
    author: "Segun A.",
    authorRole: "top-student",
    avatar: "/placeholder.svg?height=64&width=64",
    title:
      "High-yield: every past question on glycolysis regulation (2018–2024)",
    body: "Compiled every past question that has appeared in our end-of-term and resit exams. Added the answers and source pages.",
    course: "BIOC 221",
    tags: ["past-questions", "high-yield"],
    upvotes: 132,
    answers: 18,
    time: "1d ago",
  },
  {
    id: "p3",
    author: "Dr. Adeyemi (verified)",
    authorRole: "top-student",
    avatar: "/placeholder.svg?height=64&width=64",
    title: "Reminder: CA 2 covers modules 1–3 of Upper Limb",
    body: "Please do not waste time on head and neck for this CA. Focus on axilla, arm, cubital fossa, and clinical correlations.",
    course: "ANAT 201",
    tags: ["announcement"],
    upvotes: 201,
    answers: 4,
    time: "1d ago",
  },
  {
    id: "p4",
    author: "Amara N.",
    authorRole: "class-rep",
    avatar: "/placeholder.svg?height=64&width=64",
    title: "Cardiac cycle: Wiggers diagram with Nigerian lecturer voice-over",
    body: "Found a great YouTube explanation that matches exactly what Prof. Okonkwo teaches. Anyone else find it helpful?",
    course: "PHYS 211",
    tags: ["resources", "video"],
    upvotes: 58,
    answers: 11,
    time: "2d ago",
  },
];

// ---------------- Leaderboard ----------------

export const leaderboard = [
  {
    rank: 1,
    name: "Segun A.",
    score: 2480,
    streak: 42,
    avatar: "/placeholder.svg?height=64&width=64",
  },
  {
    rank: 2,
    name: "Chioma O.",
    score: 2355,
    streak: 31,
    avatar: "/placeholder.svg?height=64&width=64",
  },
  {
    rank: 3,
    name: "Tunde B.",
    score: 2210,
    streak: 28,
    avatar: "/placeholder.svg?height=64&width=64",
  },
  {
    rank: 4,
    name: "Amara N.",
    score: 2102,
    streak: 24,
    avatar: "/placeholder.svg?height=64&width=64",
  },
  {
    rank: 5,
    name: "You",
    score: 1985,
    streak: 12,
    avatar: "/placeholder.svg?height=64&width=64",
  },
  {
    rank: 6,
    name: "Ifeoma U.",
    score: 1820,
    streak: 9,
    avatar: "/placeholder.svg?height=64&width=64",
  },
  {
    rank: 7,
    name: "Kelechi E.",
    score: 1755,
    streak: 15,
    avatar: "/placeholder.svg?height=64&width=64",
  },
];

// ---------------- Today's plan ----------------

export const todaysPlan = [
  {
    id: "t1",
    type: "read" as const,
    title: "Finish Axilla boundaries & contents",
    course: "ANAT 201",
    minutes: 25,
    done: true,
  },
  {
    id: "t2",
    type: "quiz" as const,
    title: "5-question quiz · Axilla & Brachial Plexus",
    course: "ANAT 201",
    minutes: 5,
    done: false,
  },
  {
    id: "t3",
    type: "flashcards" as const,
    title: "Review 12 due flashcards",
    course: "Mixed",
    minutes: 10,
    done: false,
  },
  {
    id: "t4",
    type: "steeplechase" as const,
    title: "Steeplechase · 5 stations",
    course: "ANAT 201",
    minutes: 8,
    done: false,
  },
  {
    id: "t5",
    type: "read" as const,
    title: "Start Glycolysis: slide 1 to 14",
    course: "BIOC 221",
    minutes: 30,
    done: false,
  },
];

export function getCourse(id: string): Course | undefined {
  return courses.find((c) => c.id === id);
}

export function getMaterial(
  courseId: string,
  materialId: string,
): { course: Course; module: Module; material: Material } | undefined {
  const course = getCourse(courseId);
  if (!course) return undefined;
  for (const m of course.modules) {
    const mat = m.materials.find((x) => x.id === materialId);
    if (mat) return { course, module: m, material: mat };
  }
  return undefined;
}
