const makeOptions = (labels) =>
  labels.map((label, index) => ({ id: `o${String(index + 1).padStart(2, "0")}`, label }));

export const DO_NOT_REMEMBER_ID = "memory_unknown";

export const optionSets = Object.freeze({
  tobaccoSix: makeOptions([
    "I had never used it",
    "I had only experimented with it",
    "I had used it before but had stopped",
    "I used it occasionally",
    "I used it on most days",
    "I used it every day",
  ]),
  recencyFour: makeOptions([
    "I had never tried it by that age",
    "I had tried it before then, but not during the year before I was about 15",
    "I had used it during the year before I was about 15, but not during the most recent month",
    "I had used it during the month when I was about 15",
  ]),
  experienceThree: makeOptions([
    "This did not describe my experience",
    "This described my experience to some degree",
    "This clearly described my experience",
  ]),
  frequencyFour: makeOptions(["Almost never", "Occasionally", "Frequently", "Very frequently"]),
  appliesThree: makeOptions([
    "This did not apply to me",
    "This applied to me somewhat",
    "This applied to me strongly",
  ]),
  childhoodThree: makeOptions([
    "This did not describe me",
    "This described me to some degree",
    "This clearly described me",
  ]),
  bullyingFrequency: makeOptions([
    "This did not happen during the previous few months",
    "It happened once or twice",
    "It happened two or three times a month",
    "It happened about once a week",
    "It happened several times a week",
  ]),
  bullyingPeople: makeOptions([
    "I had not been bullied during the previous few months",
    "Usually one person was involved",
    "Usually two or three people were involved",
    "Usually four to nine people were involved",
    "Usually more than nine people were involved",
    "Different people or groups were involved at different times",
  ]),
  bullyingDuration: makeOptions([
    "I had not been bullied during the previous few months",
    "It continued for one or two weeks",
    "It continued for about one month",
    "It continued for about six months",
    "It continued for about one year",
    "It continued for several years",
  ]),
  occurrenceTwo: makeOptions(["I had not experienced this", "I had experienced this"]),
  retrospectiveFrequencySix: makeOptions([
    "It never happened",
    "It happened once",
    "It happened two or three times",
    "It happened about once a month",
    "It happened about once a week",
    "It happened several times a week",
  ]),
  tobaccoEight: makeOptions([
    "I had never used it",
    "I had only experimented with it",
    "I had used it before but had stopped",
    "I used it occasionally",
    "I used it only at social events",
    "I used it mainly on weekends",
    "I used it on most days",
    "I used it every day",
  ]),
  frequencyFive: makeOptions([
    "Never",
    "Once a month or less",
    "Two to four times a month",
    "Two to three times a week",
    "Four or more times a week",
  ]),
  educationFive: makeOptions([
    "Primary education",
    "Secondary education",
    "Upper-secondary or high-school education",
    "Undergraduate degree",
    "Postgraduate degree",
  ]),
  birthplaceTwo: makeOptions(["Born in India", "Born outside India"]),
  sexTwo: makeOptions(["Male", "Female"]),
});

const question = (id, prompt, optionSet, note) => ({ id, prompt, optionSet, note });
const supplementalQuestion = (id, prompt, optionSet, note) => ({
  id,
  prompt,
  optionSet,
  note,
  supplemental: true,
});

export const questionnaireSections = Object.freeze([
  {
    id: "s01",
    eyebrow: "Section 1 of 9",
    title: "Substance use around age 15",
    description: "Thinking back now, choose the statement that best reflects what your substance use was like when you were around 15.",
    questions: [
      question("q001", "Thinking back to when you were about 15, which statement best describes how you used cigarettes at that time?", "tobaccoSix"),
      question("q002", "Thinking back to when you were about 15, which statement best describes how you used snuff or another smokeless tobacco product at that time?", "tobaccoSix"),
      question("q003", "Thinking back to when you were about 15, how recently had you consumed alcohol at that time?", "recencyFour"),
      question("q004", "Thinking back to when you were about 15, how recently had you used cannabis at that time?", "recencyFour"),
      question("q005", "Thinking back to when you were about 15, how recently had you used another recreational drug that was not cannabis or a pain medicine?", "recencyFour"),
      question(
        "q006",
        "Thinking back to when you were about 15, how recently had you taken a pain medicine or opioid for a reason other than the medical directions given to you?",
        "recencyFour",
        "This question is about non-medical use only.",
      ),
    ],
  },
  {
    id: "s02",
    eyebrow: "Section 2 of 9",
    title: "Experiences and wellbeing around age 15",
    description: "These questions ask about experiences and feelings. They do not diagnose or label you.",
    questions: [
      question("q007", "At around age 9, did you experience seeing something that people near you did not seem to see?", "experienceThree"),
      question("q008", "At around age 15, did you feel as though somebody was secretly watching or tracking you?", "experienceThree"),
      question("q009", "At around age 15, did it seem possible that another person knew your thoughts without you telling them?", "experienceThree"),
      question("q010", "At around age 15, did ordinary media, signs, or events appear to contain a message intended specifically for you?", "experienceThree"),
      question("q011", "At around age 15, did you believe you had an ability or power that other people did not have?", "experienceThree"),
      question("q012", "At around age 15, did it feel as though an outside force was directing your thoughts or actions?", "experienceThree"),
      question("q013", "At around age 15, did you feel able to know another person's thoughts without being told?", "experienceThree"),
      question("q014", "At around age 15, did you experience seeing something that other people present did not seem to see?", "experienceThree"),
      question("q015", "At around age 15, how often did you have periods of feeling unusually excited or intensely upbeat?", "frequencyFour"),
      question("q016", "At around age 15, how often were you unusually irritable for an extended period?", "frequencyFour"),
      question("q017", "At around age 15, how often did you feel capable of things that were not realistically possible for you?", "frequencyFour"),
      question("q018", "At around age 15, how often did you sleep much less than usual and still feel rested?", "frequencyFour"),
      question("q019", "At around age 15, how often did you have a level of energy that was far above your usual level?", "frequencyFour"),
      question("q020", "At around age 15, how often did your thoughts move so quickly that they were difficult to slow down?", "frequencyFour"),
      question("q021", "At around age 15, how often did you speak so quickly that keeping to one topic became difficult?", "frequencyFour"),
      question("q022", "At around age 15, how often did your sexual words or actions not fit the situation?", "frequencyFour"),
      question("q023", "At around age 15, how often did you have intense and prolonged bursts of anger?", "frequencyFour"),
      question("q024", "At around age 15, how often did you hear speech or voices that nobody nearby appeared to hear?", "frequencyFour"),
      question("q025", "At around age 15, did you regularly experience headaches or similar physical discomfort?", "appliesThree"),
      question("q026", "At around age 15, did worry affect you a great deal?", "appliesThree"),
      question("q027", "At around age 15, did you regularly feel low, unhappy, or tearful?", "appliesThree"),
      question("q028", "At around age 15, did you often feel less confident in yourself?", "appliesThree"),
      question("q029", "At around age 15, were you easily frightened by many things?", "appliesThree"),
    ],
  },
  {
    id: "s03",
    eyebrow: "Section 3 of 9",
    title: "Attention and activity during childhood",
    description: "Think about yourself at around age 9 compared with other children of a similar age.",
    questions: [
      question("q030", "Did you often overlook details or make mistakes because you had not noticed something important?", "childhoodThree"),
      question("q031", "Was it difficult for you to stay focused on an activity or task?", "childhoodThree"),
      question("q032", "Did people sometimes think you had not heard them even when they spoke directly to you?", "childhoodThree"),
      question("q033", "Was it difficult to carry instructions through to the end or finish assigned tasks?", "childhoodThree"),
      question("q034", "Did arranging tasks, belongings, or activities feel difficult?", "childhoodThree"),
      question("q035", "Did you strongly avoid activities that required concentration for a long time?", "childhoodThree"),
      question("q036", "Did you frequently misplace items you needed?", "childhoodThree"),
      question("q037", "Was your attention easily pulled away by things happening around you?", "childhoodThree"),
      question("q038", "Did you frequently forget ordinary activities or responsibilities?", "childhoodThree"),
      question("q039", "Was remaining seated or physically still especially difficult when it was expected?", "childhoodThree"),
      question("q040", "Did you frequently fidget or keep parts of your body moving?", "childhoodThree"),
      question("q041", "Did you run or climb in situations where other children usually remained still?", "childhoodThree"),
      question("q042", "Was taking part quietly in play or leisure activities difficult?", "childhoodThree"),
      question("q043", "Did you seem constantly active, as though it was hard to slow down?", "childhoodThree"),
      question("q044", "Did you speak much more than the situation called for?", "childhoodThree"),
      question("q045", "Did you often respond before somebody had finished asking a question?", "childhoodThree"),
      question("q046", "Was waiting for your turn particularly difficult?", "childhoodThree"),
      question("q047", "Did you frequently enter other people's conversations or activities without waiting?", "childhoodThree"),
      question("q048", "Did you lose interest and become bored very quickly?", "childhoodThree"),
    ],
  },
  {
    id: "s04",
    eyebrow: "Section 4 of 9",
    title: "Communication and flexibility during childhood",
    description: "Think about yourself at around age 9 compared with other children of a similar age.",
    questions: [
      question("q049", "Was the development of your spoken language noticeably later than expected?", "childhoodThree"),
      question("q050", "Was having a two-way conversation difficult for you?", "childhoodThree"),
      question("q051", "Did you repeatedly use the same words or expressions?", "childhoodThree"),
      question("q052", "Was make-believe or imaginative play difficult?", "childhoodThree"),
      question("q053", "Did your voice often sound unusually loud, quiet, high, low, or otherwise different?", "childhoodThree"),
      question("q054", "Was it hard to keep a conversation connected to its main topic?", "childhoodThree"),
      question("q055", "Was communicating your thoughts, feelings, or needs to other people difficult?", "childhoodThree"),
      question("q056", "Was joining in socially with other children difficult?", "childhoodThree"),
      question("q057", "Did you rarely invite other people to share your enjoyment, interests, or achievements?", "childhoodThree"),
      question("q058", "Did you usually want social contact to happen according to your own preferred conditions?", "childhoodThree"),
      question("q059", "Was understanding unspoken social expectations difficult?", "childhoodThree"),
      question("q060", "Were you more easily persuaded or led by other people than children of a similar age?", "childhoodThree"),
      question("q061", "Did your interests or activities sometimes absorb nearly all of your attention?", "childhoodThree"),
      question("q062", "Was it difficult to move away from a particular topic or problem once it held your attention?", "childhoodThree"),
      question("q063", "Did you make repeated or unusual body movements?", "childhoodThree"),
      question("q064", "Did you focus intensely on individual details rather than the wider situation?", "childhoodThree"),
      question("q065", "Did unexpected changes to routines or plans cause strong discomfort?", "childhoodThree"),
    ],
  },
  {
    id: "s05",
    eyebrow: "Section 5 of 9",
    title: "Bullying and other harmful experiences around age 15",
    description: "Thinking back now, answer about experiences that had happened by the time you were around 15.",
    questions: [
      supplementalQuestion(
        "q086",
        "By the time you were around 15, how often had a parent, caregiver, or another adult repeatedly insulted, humiliated, threatened, rejected, or emotionally harmed you?",
        "retrospectiveFrequencySix",
        "This supplemental question provides context only and is not used by the current research model.",
      ),
      supplementalQuestion(
        "q087",
        "By the time you were around 15, how often had a parent, caregiver, or another adult deliberately hit, kicked, pushed, or otherwise physically hurt you?",
        "retrospectiveFrequencySix",
        "This supplemental question provides context only and is not used by the current research model.",
      ),
      supplementalQuestion(
        "q088",
        "By the time you were around 15, how often had an older person or a person in authority pressured, forced, or involved you in sexual touching or sexual activity that you did not want or could not consent to?",
        "retrospectiveFrequencySix",
        "This supplemental question provides context only and is not used by the current research model.",
      ),
      question("q066", "How often were you bullied in a way not covered by the other examples in this section?", "bullyingFrequency"),
      question("q067", "How often did repeated bullying happen to you?", "bullyingFrequency"),
      question("q068", "How often did somebody mock you, use a hurtful nickname, or deliberately embarrass you?", "bullyingFrequency"),
      question("q069", "How often were you deliberately excluded, ignored, or treated in another emotionally harmful way?", "bullyingFrequency"),
      question("q070", "How often did somebody spread an untrue or harmful story about you?", "bullyingFrequency"),
      question("q071", "When bullying happened, how many people were usually involved?", "bullyingPeople"),
      question("q072", "When bullying happened, for how long did it continue?", "bullyingDuration"),
    ],
  },
  {
    id: "s06",
    eyebrow: "Section 6 of 9",
    title: "Difficult or harmful experiences reported at age 18",
    description: "Consider experiences that had happened by the time you were 18.",
    questions: [
      question("q074", "Had you experienced violence that you believed was motivated by prejudice about an aspect of who you are?", "occurrenceTwo"),
      question("q075", "Had somebody repeatedly humiliated, rejected, intimidated, or emotionally harmed you?", "occurrenceTwo"),
      question("q076", "Had you directly witnessed a threatening or violent crime in person rather than through media?", "occurrenceTwo"),
      question("q073", "Had you experienced another serious or harmful event not covered by the other questions in this section?", "occurrenceTwo"),
    ],
  },
  {
    id: "s07",
    eyebrow: "Section 7 of 9",
    title: "Substance use around age 18",
    description: "Choose the statement that best reflects your experience at that age.",
    questions: [
      question("q077", "Which statement best matches your cigarette use at around age 18?", "tobaccoEight"),
      question("q078", "Which statement best matches your use of snuff or another smokeless tobacco product at around age 18?", "tobaccoEight"),
      question("q079", "At around age 18, how frequently did you consume alcohol?", "frequencyFive"),
      question(
        "q080",
        "At around age 18, how frequently did you use a recreational drug or medication for a non-medical reason?",
        "frequencyFive",
        "Non-medical use includes taking more than directed, taking medication more often than directed, taking it to become intoxicated or explore its effects, or using medication obtained from somebody else or an unofficial source.",
      ),
    ],
  },
  {
    id: "s08",
    eyebrow: "Section 8 of 9",
    title: "Family background",
    description: "These questions ask about parental education and birthplace.",
    questions: [
      question("q081", "What was the highest level of education completed by your father?", "educationFive"),
      question("q082", "Was your father born in India or outside India?", "birthplaceTwo"),
      question("q083", "What was the highest level of education completed by your mother?", "educationFive"),
      question("q084", "Was your mother born in India or outside India?", "birthplaceTwo"),
    ],
  },
  {
    id: "s09",
    eyebrow: "Section 9 of 9",
    title: "Sex supported by the current research model",
    description: "The current research model supports only the two training categories shown below.",
    questions: [
      question(
        "q085",
        "What sex was recorded for you at birth?",
        "sexTwo",
        "The answer is not inferred from gender identity, name, language, appearance, or any other response.",
      ),
    ],
  },
]);

export const allQuestions = Object.freeze(
  questionnaireSections.flatMap((section) =>
    section.questions.map((item) => ({ ...item, sectionId: section.id, sectionTitle: section.title })),
  ),
);

export const totalQuestionCount = allQuestions.length;

export const modelQuestionCount = allQuestions.filter((item) => !item.supplemental).length;

export function getOptionsForQuestion(item) {
  const options = optionSets[item.optionSet];
  if (!options) {
    throw new Error(`Missing option set for ${item.id}`);
  }
  return options;
}
