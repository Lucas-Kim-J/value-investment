import { useEffect, useState } from "react";
import { me } from "./api";

/** undefined = still loading, null = not logged in, string = username */
export function useMe(): string | null | undefined {
  const [user, setUser] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    me().then((u) => {
      if (alive) setUser(u);
    });
    return () => {
      alive = false;
    };
  }, []);
  return user;
}
