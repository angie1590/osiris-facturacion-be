import React, { useEffect } from 'react';

export default function IntroRedirectPage() {
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.location.replace('/docs/intro');
    }
  }, []);

  return null;
}
