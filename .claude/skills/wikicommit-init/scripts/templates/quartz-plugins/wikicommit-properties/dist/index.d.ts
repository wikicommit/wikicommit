import { FullSlug, QuartzTransformerPlugin } from '@quartz-community/types';
export { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps, QuartzTransformerPlugin } from '@quartz-community/types';
export { WikiCommitPropertiesComponent, WikiCommitPropertiesComponentOptions } from './components/index.js';

interface WikiCommitPropertiesOptions {
    /** Include all frontmatter properties in the display. When false, only `includedProperties` are shown. */
    includeAll: boolean;
    /** Properties to include when `includeAll` is false. Ignored when `includeAll` is true. */
    includedProperties: string[];
    /** Properties to exclude from display. Applied after inclusion logic (and after flattening — see transformer.ts). */
    excludedProperties: string[];
    /**
     * Keys inside an object-valued property (WikiCommit's `properties:`) that
     * hold prose summarising the page body rather than a fact the box can
     * state in a few words — `properties.description` is the body's lead in
     * 2-3 sentences. They are left out of the box (the body already says
     * them, Issue #1292) but stay in the frontmatter, so JSON-LD and
     * llms.txt still read them. A top-level field of the same name is not
     * affected; use `excludedProperties` for that.
     */
    proseProperties: string[];
    /** Hide the visual properties panel while still processing frontmatter and resolving links. */
    hidePropertiesView: boolean;
    /** Frontmatter delimiters. Defaults to "---". */
    delimiters: string | [string, string];
    /** Frontmatter language. Defaults to "yaml". */
    language: "yaml" | "toml";
}

declare const WikiCommitProperties: QuartzTransformerPlugin<Partial<WikiCommitPropertiesOptions>>;
declare module "vfile" {
    interface DataMap {
        aliases: FullSlug[];
        frontmatterLinks: string[];
        wikicommitProperties: {
            properties: Record<string, unknown>;
            hideView: boolean;
            showProperties?: boolean;
            collapseProperties?: boolean;
            resolvedLinks?: Record<string, string>;
        };
    }
}

export { WikiCommitProperties, type WikiCommitPropertiesOptions };
