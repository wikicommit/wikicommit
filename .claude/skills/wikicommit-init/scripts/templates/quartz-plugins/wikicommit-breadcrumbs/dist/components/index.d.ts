import { QuartzComponent } from '@quartz-community/types';

interface BreadcrumbOptions {
    /** Symbol between crumbs */
    spacerSymbol: string;
    /** Name of first crumb */
    rootName: string;
    /** Whether to display the current page in the breadcrumbs */
    showCurrentPage: boolean;
}
declare const _default: (opts?: Partial<BreadcrumbOptions>) => QuartzComponent;

export { type BreadcrumbOptions as B, _default as WikiCommitBreadcrumbs };
