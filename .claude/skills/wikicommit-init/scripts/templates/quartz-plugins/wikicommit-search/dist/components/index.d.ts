import { QuartzComponent } from '@quartz-community/types';

type SearchField = "title" | "content" | "tags";
interface SearchOptions {
    enablePreview: boolean;
    fieldPriority: SearchField[];
}
declare const _default: (userOpts?: Partial<SearchOptions>) => QuartzComponent;

export { type SearchField, type SearchOptions, _default as WikiCommitSearch };
