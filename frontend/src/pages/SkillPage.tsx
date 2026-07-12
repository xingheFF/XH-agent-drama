import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { SkillChat, type SkillDef } from '@/components/SkillChat';

export default function SkillPage() {
  const navigate = useNavigate();
  const [skill, setSkill] = useState<SkillDef | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    // StrictMode 下 useEffect 会执行两次，用 ref 防止重复处理
    if (loadedRef.current) return;
    loadedRef.current = true;

    const raw = sessionStorage.getItem('skillChatData');
    if (raw) {
      try {
        setSkill(JSON.parse(raw));
      } catch {
        navigate('/home');
      }
      sessionStorage.removeItem('skillChatData');
    } else {
      navigate('/home');
    }
  }, [navigate]);

  if (!skill) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-canvas-bg">
        <div className="text-theme-sub text-sm">加载中...</div>
      </div>
    );
  }

  return <SkillChat skill={skill} page />;
}
