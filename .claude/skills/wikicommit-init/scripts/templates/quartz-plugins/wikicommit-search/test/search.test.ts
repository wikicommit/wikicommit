import { describe, it, expect } from "vitest";
import WikiCommitSearch from "../src/components/WikiCommitSearch";

describe("WikiCommitSearch Component", () => {
  it("exports a component factory function", () => {
    expect(typeof WikiCommitSearch).toBe("function");
  });

  it("creates a component with default options", () => {
    const SearchComponent = WikiCommitSearch();
    expect(typeof SearchComponent).toBe("function");
  });

  it("creates a component with custom options", () => {
    const SearchComponent = WikiCommitSearch({ enablePreview: false });
    expect(typeof SearchComponent).toBe("function");
  });

  it("attaches CSS and script to component", () => {
    const SearchComponent = WikiCommitSearch();
    expect(SearchComponent.css).toBeDefined();
    expect(SearchComponent.afterDOMLoaded).toBeDefined();
  });
});
