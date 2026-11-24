# Codex adaptation

Reviewed upstream commit: `03ceb42f7fa2c4439aca01752118044baabffb8f`. The adapted skill is under [skills](skills/).

NVIDIA SkillSpector 2.13.7 in static mode reported SAFE with 100% coverage on the adapted skill directory. Upstream full repository: 100/100 risk score, DO_NOT_INSTALL, 98% coverage. The Codex adaptation removes automatic setup, credential handling, browser cookies and cloud upload. Local extraction was verified on eight pilot frames. Public URL mode requires yt-dlp and has not been tested here.

The scan reported a tool-permission declaration finding and subprocess findings for the FFmpeg workflow. These results cover the adapted directory and do not certify external dependencies. MIT attribution is retained within the skill.
