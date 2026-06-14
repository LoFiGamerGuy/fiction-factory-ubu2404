import { useEffect, useState } from "react";
import { getEvoSkill } from "../api/client";
import type { EvoSkillEntry } from "../types";

interface SkillLibraryProps {
  seriesId: string;
}

export function SkillLibrary({ seriesId }: SkillLibraryProps) {
  const [skills, setSkills] = useState<EvoSkillEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadSkills() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await getEvoSkill(seriesId);
        if (!isCancelled) {
          setSkills(response);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load EvoSkill library");
          setSkills([]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadSkills();
  }, [seriesId]);

  return (
    <section className="panel historical-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Learning Loop</p>
          <h2>Skill Library</h2>
        </div>
        <span className="status-pill">{isLoading ? "Loading" : `${skills.length} skills`}</span>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <ol className="event-list">
        {skills.length > 0 ? (
          skills.map((skill) => (
            <li key={skill.skill_id}>
              <div className="event-row">
                <strong>{skill.skill_id}</strong>
                <span>{wordCount(skill.content)} words</span>
              </div>
              <p className="muted">{excerpt(skill.content)}</p>
              <details>
                <summary>Skill markdown</summary>
                <pre>{skill.content}</pre>
              </details>
            </li>
          ))
        ) : (
          <li className="muted">No promoted EvoSkill markdown files loaded for {seriesId}.</li>
        )}
      </ol>
    </section>
  );
}

function excerpt(content: string): string {
  const compact = content.replace(/\s+/g, " ").trim();
  return compact.length > 180 ? `${compact.slice(0, 180)}...` : compact || "Empty skill file.";
}

function wordCount(content: string): number {
  return content.split(/\s+/).filter(Boolean).length;
}
