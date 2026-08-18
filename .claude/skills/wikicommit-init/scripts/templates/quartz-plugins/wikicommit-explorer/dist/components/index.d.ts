import { QuartzComponent } from '@quartz-community/types';

interface FileTrieNode {
    slugSegment?: string;
    slugSegments?: string[];
    displayName?: string;
    isFolder: boolean;
    data: Record<string, unknown> | null;
    children: FileTrieNode[];
}
interface ExplorerOptions {
    title?: string;
    folderDefaultState: "collapsed" | "open";
    folderClickBehavior: "collapse" | "link";
    useSavedState: boolean;
    sortFn?: (a: FileTrieNode, b: FileTrieNode) => number;
    filterFn?: (node: FileTrieNode) => boolean;
    mapFn?: (node: FileTrieNode) => FileTrieNode;
    order?: Array<"filter" | "map" | "sort">;
}
declare const _default: (userOpts?: Partial<ExplorerOptions>) => QuartzComponent;

export { type ExplorerOptions, _default as WikiCommitExplorer };
