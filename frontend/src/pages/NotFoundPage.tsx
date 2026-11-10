// 404 page. Minimal, editorial.

import { Link } from "react-router-dom";
import { setDocumentTitle } from "@/utils/title";
import { useEffect } from "react";

export function NotFoundPage(): JSX.Element {
  useEffect(() => {
    setDocumentTitle("Not found");
  }, []);

  return (
    <div className="not-found-page" role="main">
      <h1 className="not-found-page__title">Not found</h1>
      <p className="not-found-page__lede editorial-muted">
        The requested page does not exist in this workbench.
      </p>
      <Link to="/overview" className="not-found-page__link">
        Return to Study Overview
      </Link>
    </div>
  );
}
