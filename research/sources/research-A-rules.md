# Bharat AI-SoC Challenge 2026–27 — PS3 rules and submission research

**Checked:** 9 November 2026. **Entry context:** solo PS3 entrant registered before registration closed.

## Evidence tags

- **[sourced]** means the linked source states the claim; the quoted text is verbatim.
- **[inferred]** means the conclusion follows from the cited wording but is not an explicit organizer ruling.
- **[unknown]** means the public materials checked do not answer it. This does not rule out instructions sent privately to registered participants.

Primary sources: [official challenge page](https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html), its [GitHub source file](https://github.com/arm-education/Arm-Developer-Labs/blob/main/docs/Bharat_AI_SoC_2026_27.html), the linked [Getting Started Resources](https://arm-education.github.io/online-resources-arm/), and the linked [ExecuTorch course](https://learn.arm.com/courses/executorch-on-arm/).

## Challenge identity

- The page labels this the “2nd Edition” with the theme “Applied AI on SoC”; it says the challenge is run by MeitY through the Chips to Startup (C2S) Programme in collaboration with Arm, with IIT Delhi as mentor institute. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “2nd Edition”; “Applied AI on SoC”; “through its Chips to Startup (C2S) Programme, in collaboration with Arm”; “with IIT Delhi as the mentor institute”]

## 1. Timeline and updates

### Deadline history relevant to older page copies

- On **16 October**, the GitHub commit titled “Update Bharat AI-SoC Challenge timeline” changed Phase 1 from **30 November 2026** to **23 November 2026**, and Phase 2 from **10 February 2027** to **5 February 2027**. [sourced: https://github.com/arm-education/Arm-Developer-Labs/commit/58b22a92f5d0e4a8c364a74817c8d17ba14877d9 — diff: “30 November 2026” → “23 November 2026”; “10 February 2027” → “5 February 2027”]
- That date change predates the requested 23 October–9 November window. It explains older copies/extracts with the former dates; the live page and current source match the 23 November / 5 February schedule. [inferred: https://github.com/arm-education/Arm-Developer-Labs/commit/58b22a92f5d0e4a8c364a74817c8d17ba14877d9 and current official page https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html]

- The official timeline gives **Phase 1 — Open Qualifying: 23 November 2026**. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Phase 1 — Open Qualifying submission deadline | 23 November 2026 | Teams must submit their Phase 1 Open Qualifying project by this date.”]
- The page’s challenge-format section repeats: **“Submission deadline: 23 November 2026”** and says teams submit “their report, source code and demo.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — exact quote]
- The page states the deadline by date only; it publishes no cutoff hour or timezone. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — the deadline wording is “Submission deadline: 23 November 2026”; no time or timezone is given there or in the current GitHub source file]

Other timeline dates on the official page:

- Launch: 19 September 2026. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Launch | 19 September 2026”]
- Registration closed: 19 October 2026. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Registration closes | 19 October 2026”]
- Phase 1 shortlisted-team results: mid-December 2026. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Phase 1 shortlisted-team results | Mid-December 2026”]
- Phase 2 — PoC Development submission deadline: 5 February 2027. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Phase 2 — PoC Development submission deadline | 5 February 2027”]
- Finals and winners’ announcement: 15–16 February 2027. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Finals & Winners’ Announcement | 15–16 February 2027”]

### Public changes after 23 October 2026

The current page still states 23 November 2026; the repository’s post-23-October history for this challenge page shows the edits below. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Submission deadline: 23 November 2026”; post-23-October commit links below]

- **29 October:** the commit title is “Added the ExecuTorch course”; it added the notice “Get started: Online ExecuTorch course.” [sourced: https://github.com/arm-education/Arm-Developer-Labs/commit/125d80e31459fe44b1baf9af36a0856f08a71c2f — commit title and added heading]
- **2 November:** “Add mentoring videos to Bharat AI-SoC Challenge 2026-27.” [sourced: https://github.com/arm-education/Arm-Developer-Labs/commit/fcdf7e9a07bfe92c7ba6196419c4e8f9afd2f09c — commit title; it adds “Mentoring Session Video” sections]
- **3 November:** “Change P1 video.” [sourced: https://github.com/arm-education/Arm-Developer-Labs/commit/8a8cfd47a7c5bec1006c3c4002394a6cf1937393 — commit title]
- Those three inspected diffs concern the course/video sections; they do not change the deadline or submission requirements. The live page and current `main` source both still contain “23 November 2026” and “5 February 2027.” [sourced: https://github.com/arm-education/Arm-Developer-Labs/commit/125d80e31459fe44b1baf9af36a0856f08a71c2f ; https://github.com/arm-education/Arm-Developer-Labs/commit/fcdf7e9a07bfe92c7ba6196419c4e8f9afd2f09c ; https://github.com/arm-education/Arm-Developer-Labs/commit/8a8cfd47a7c5bec1006c3c4002394a6cf1937393 ; https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — current deadline quote]
- I found no official extension or deadline-change announcement dated after 23 October in the checked public page, repository history, or targeted web searches. Treat this as “none found,” not proof that no private message was sent to registrants. [unknown: current page says “Challenge-related notifications and updates will be posted on this page”; the live page and checked GitHub history are linked above]

## 2. Phase 1 submission requirements

- The page says teams submit “their report, source code and demo”; PS3’s deliverables list is “Source code,” “Application,” “Demonstration video,” and “Technical report.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — exact quotes]
- The project “must be hosted on GitHub and submitted using the challenge submission form.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — exact quote]
- The public challenge page does not link a Phase 1 form or list its fields. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — it mentions “the challenge submission form” but publishes no form fields or form link]
- Report file type, structure/template, and page limit are not published in the checked public challenge page or the challenge-specific GitHub file. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html ; https://github.com/arm-education/Arm-Developer-Labs/blob/main/docs/Bharat_AI_SoC_2026_27.html — only “report” / “Technical report” is specified]
- Demo-video duration, file format, upload location, and whether a link or file is expected are not published there. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — the stated deliverable is “Demonstration video”]
- GitHub hosting is mandatory, but the page does not say whether the repository must be public, may be private, or how reviewer access should be granted. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “The project must be hosted on GitHub”]
- Source code is explicitly required; the page does not specify language, packaging, build/run instructions, license, commit history, or whether a particular branch/tag must be reviewed. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Source code”; unknown for the unstated details]
- I found no public current-edition PDF or separate submission FAQ in the challenge-specific repository tree; the challenge’s public page itself contains FAQ items 1–9. [unknown: https://github.com/arm-education/Arm-Developer-Labs ; https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html]

### FAQ item beyond the earlier snapshot

The live page continues beyond FAQ 8 with **“9. Participant Materials and Intellectual Property.”** Its full answer reads:

> Participants are responsible for ensuring that they have all necessary rights, permissions and authorisations to use and submit any intellectual property, software, code, data, materials or other content used in connection with their participation in the Bharat AI-SoC Challenge ("Participant Materials").
>
> Participants must not submit or disclose any confidential, proprietary or third-party information unless they are authorised to do so and such disclosure does not breach any confidentiality, employment, contractual or other obligation owed to any third party.
>
> Participation in the Challenge does not require participants to disclose their own confidential information. Any Participant Materials voluntarily submitted or disclosed as part of the Challenge are provided at the participant's own discretion and responsibility.
>
> Each participant remains responsible for ensuring that their participation and submission do not infringe, misappropriate or otherwise violate any third-party intellectual property or other rights.

[sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — FAQ 9, verbatim]

## 3. PS3 technical rules and IP

### Required model and runtime

- PS3’s exact technical requirement is: **“A model from the Llama family must be used for the advisory or reasoning component and deployed on-device using ExecuTorch as the reference runtime.”** [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS3, Required Technologies]
- PS3 requires Llama for the advisory/reasoning role; it does not say that Llama must itself perform every detection/classification task. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — exact requirement above]
- The page gives a more specific example under **PS1**, not PS3: “for example, Llama 3.2 1B/3B-Instruct or a fine-tuned or distilled variant.” Since the wording says “for example,” these are examples rather than an express exclusive version list. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS1 technical-requirement parenthetical; inferred that the examples are non-exclusive from “for example”]
- A Llama 3.2 1B/3B-Instruct model and fine-tuned/distilled variants are explicitly named examples on the page, but PS3 itself does not state a version or variant whitelist. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS1 example and separate PS3 requirement]
- SpinQuant, QAT-LoRA, or specific quantized Llama checkpoints are not named in the challenge rules checked. The linked ExecuTorch course teaches quantization generally; it does not establish that a particular quantized checkpoint is organizer-approved. [unknown: challenge page quote above; https://learn.arm.com/courses/executorch-on-arm/ — “Apply quantization techniques to reduce model size and deployment computation”]
- A fine-tuned/distilled Llama variant appears to fit the family rule if the resulting model remains a Llama-family model and is deployed on-device with ExecuTorch; that reading for PS3 is an inference from the PS1 example, not a PS3-specific ruling. Ask the organizers to confirm if using a materially modified or quantized variant is a compliance risk. [inferred: PS1’s “fine-tuned or distilled variant” example plus PS3’s Llama-family requirement; https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html]
- A small non-LLM detector alongside the required Llama appears compatible: the stated Llama role is advisory/reasoning, while PS3’s objectives separately include monitoring/classifying network traffic and detecting phishing URLs and scam messages. The page does not expressly approve a specific extra classifier. [inferred: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS3 objective/project description and Required Technologies]
- The page does not expressly say whether another LLM such as Qwen may be used alongside Llama. Qwen cannot replace the required Llama-family model; whether an additional LLM is acceptable is not answered publicly. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — mandatory Llama-family quote above; no rule found on additional LLMs]

### On-device, network, and hardware constraints

- PS3’s objective says the system runs “entirely on Arm-based edge hardware without cloud dependency”; the project description requires “Processing data locally on the device without relying on cloud services.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS3 Objective and Project Description]
- This establishes local/on-device operation without cloud dependency. The page does not define whether every feature must work with all network interfaces disabled, or how online-updated threat feeds should be handled. [inferred for local/no-cloud requirement from the quote above; unknown for a formal offline test or feed policy]
- PS3 lists these hardware options: Arm-based Android smartphones; Raspberry Pi 5 CPU-only; Raspberry Pi 5 with AI HAT+ / AI HAT+ 2; and Arm-based Linux devices. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS3 Hardware list]
- For Hailo use, the page says: “If a Hailo accelerator is used for compatible workloads, it runs through HailoRT on the Hailo NPU, while Llama runs through ExecuTorch on the Raspberry Pi Arm CPU. These are separate pipelines and should be clearly documented.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS3 Hardware]
- PS3 lists CICIDS / UNSW-NB15 / NSL-KDD, PhishTank / OpenPhish, the UCI SMS Spam Collection, libpcap / Scapy, and Hailo SDK as optional technologies. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — PS3 Optional Technologies]
- Use of named third-party datasets is contemplated, but FAQ 9 makes participants responsible for rights, permissions, and authorization. The page does not provide dataset-specific license guidance. [sourced: optional dataset list and FAQ 9 at https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html; unknown for dataset-specific guidance]

### Original work, third-party material, and AI assistance

- Original-work requirements say entries must “Be the original work of the entrant(s),” “Be solely owned by the entrant(s),” and “Not violate the intellectual property rights of any other person or entity.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — Original Work Requirements]
- FAQ 9 adds that participants must hold necessary rights/permissions for submitted code, data, software, and other materials; must not disclose confidential or third-party information without authorization; and remain responsible for avoiding infringement or misappropriation. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — FAQ 9, full text quoted above]
- The page does not explain how “solely owned” applies to submissions that include third-party licensed model weights, libraries, or datasets; FAQ 9 makes rights and permissions the participant’s responsibility. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html]
- No rule on AI-assisted coding, generative-AI use, or disclosure of AI assistance was found in the public challenge page, repository challenge file, or linked learning resources checked. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html ; https://github.com/arm-education/Arm-Developer-Labs/blob/main/docs/Bharat_AI_SoC_2026_27.html ; https://arm-education.github.io/online-resources-arm/]

## 4. Listed disqualification risks

- “Duplicate registrations may result in rejection or disqualification.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — Challenge Guidelines & Terms]
- “Incorrect or duplicate entries may result in disqualification.” [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — Challenge Guidelines & Terms]
- The page also says only eligible participants may participate, only the Team Leader should register, and all registration details must be accurate. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — Challenge Guidelines & Terms]
- Teams may have 1–3 members, so a one-person team is within the stated team-size range. [sourced for “Teams may have 1–3 members”; inferred that one person is permitted, https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — Eligibility Criteria]
- The page does not attach a stated disqualification penalty to technical noncompliance with the Llama/runtime or local-processing requirements; it does state those requirements. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html]

## 5. Organizer-linked getting-started material

- The challenge page links “Getting Started Resources” to Arm Education’s resource hub and now also links the ExecuTorch course directly. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “Getting Started Resources”; course notice added in https://github.com/arm-education/Arm-Developer-Labs/commit/125d80e31459fe44b1baf9af36a0856f08a71c2f]
- The course describes itself as covering “Practical Edge Linux, mobile, and embedded NPU deployment workflows that turn PyTorch models into lightweight ExecuTorch applications.” [sourced: https://learn.arm.com/courses/executorch-on-arm/ — What you’ll learn]
- Its prerequisites specify a Raspberry Pi 5 with 64-bit Raspberry Pi OS Trixie for Modules 1 and 2, an Android smartphone or Android Studio emulator for Module 3, and an Ubuntu LTS development machine or cloud instance for Module 4. [sourced: https://learn.arm.com/courses/executorch-on-arm/ — Prerequisites]
- The course modules include transformer inference on Arm CPUs with ExecuTorch/XNNPACK, an Android segmentation app, and an Ethos-U deployment workflow. It is an implementation resource, not a published PS3 model-eligibility ruling. [sourced: https://learn.arm.com/courses/executorch-on-arm/ — Modules; inferred that tutorial material does not itself change contest rules]
- The resource hub lists **“Optimizing Generative AI on Arm Processors — From Edge to Cloud”** and describes it as covering “quantization, SIMD, KleidiAI, and CPU-focused techniques.” [sourced: https://arm-education.github.io/online-resources-arm/ — course title and summary]
- The hub also lists **“AI at the Edge on ARM — Understanding and Deploying LLMs for Mobile Devices,”** described as LLM deployment and optimization on Arm-powered mobile devices using compression techniques and practical edge-AI development. [sourced: https://arm-education.github.io/online-resources-arm/ — course title and summary]
- The hub also points to **“Machine Learning at the Edge on Arm — A Practical Introduction,”** which covers training, optimizing, and deploying ML models on Arm-based microcontrollers. [sourced: https://arm-education.github.io/online-resources-arm/ — course title and summary]
- Direct links listed by the hub include [edX: AI on Arm](https://www.edx.org/learn/computer-science/arm-education-ai-on-arm), [Coursera: Optimizing Generative AI](https://www.coursera.org/learn/optimizing-generative-ai), and [edX: AI at the Edge on ARM](https://www.edx.org/learn/computer-science/arm-education-ai-at-the-edge-on-arm). [sourced: https://arm-education.github.io/online-resources-arm/ — course links]

## Practical unresolved points

- Confirm the Phase 1 cutoff hour/timezone, form fields, report template/page cap, video specs, and GitHub visibility/access instructions from the participant submission instructions; none are on the public materials checked. [unknown: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html]
- For a binding PS3 answer on SpinQuant/QAT-LoRA, other Llama versions, or additional models such as Qwen, the page directs technical questions to `tech-queries@armbharatchallenge.com` and says to include the problem statement number in the subject. No message was sent as part of this research. [sourced: https://arm-education.github.io/Arm-Developer-Labs/Bharat_AI_SoC_2026_27.html — “For technical questions relating to a problem statement, email tech-queries@armbharatchallenge.com and include the relevant problem statement number in the subject line.”]
