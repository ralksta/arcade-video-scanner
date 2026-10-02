import Brand from './Brand';
import css from './Home.module.less';

/**
 * Platzhalter, solange die Mediathek lädt: das Logo und graue, schimmernde
 * Kacheln an der Stelle der Reihen — statt einer leeren schwarzen Fläche.
 */
const Skeleton = () => (
	<div className={css.skeleton} aria-busy="true">
		<div className={css.skeletonHero}>
			<Brand size="large" />
			<div className={css.skeletonHint}>Lade Mediathek …</div>
		</div>
		{[0, 1].map(row => (
			<div key={row} className={css.skeletonRow}>
				<div className={css.skeletonTitle} />
				<div className={css.skeletonCards}>
					{[0, 1, 2, 3, 4, 5].map(i => <div key={i} className={css.skeletonCard} />)}
				</div>
			</div>
		))}
	</div>
);

export default Skeleton;
