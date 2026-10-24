import {useState, useEffect, useCallback} from 'react';
import PropTypes from 'prop-types';
import Spotlight from '@enact/spotlight';
import SpotlightContainerDecorator from '@enact/spotlight/SpotlightContainerDecorator';
import Spottable from '@enact/spotlight/Spottable';

import css from './ImageViewer.module.less';

const Container = SpotlightContainerDecorator({restrict: 'self-only'}, 'div');
const Stage = Spottable('div');
const CONTAINER_ID = 'image-viewer';

/**
 * Bilder im Vollbild, in voller Auflösung (über /stream, wie Videos).
 *
 * Vorher landete „Abspielen“ bei einem Bild im Videoplayer — der zeigte
 * nichts. Links/Rechts blättert durch die Liste, Zurück schließt. Titel und
 * Position blenden nach drei Sekunden aus, wie bei einer Diashow.
 *
 * @param {Object[]} items - Bild-Einträge
 * @param {number} startIndex
 * @param {Function} srcFor - (eintrag) => URL in voller Größe
 * @param {Function} titleFor - (eintrag) => Anzeigename
 * @param {Function} onClose
 */
const ImageViewer = ({items, startIndex, srcFor, titleFor, onClose}) => {
	const [index, setIndex] = useState(startIndex);
	const [chrome, setChrome] = useState(true);

	const step = useCallback((delta) => {
		setIndex(i => (i + delta + items.length) % items.length);
		setChrome(true);
	}, [items.length]);

	useEffect(() => {
		const timer = setTimeout(() => setChrome(false), 3000);
		return () => clearTimeout(timer);
	}, [index, chrome]);

	useEffect(() => {
		const focus = setTimeout(() => Spotlight.focus(CONTAINER_ID), 0);
		const onKey = (ev) => {
			const k = ev.keyCode;
			if (k === 461 || k === 27) onClose();
			else if (k === 37) step(-1);
			else if (k === 39) step(1);
			else if (k === 13 || k === 38 || k === 40) setChrome(c => !c);
			else return;
			ev.preventDefault();
			ev.stopImmediatePropagation();
		};
		document.addEventListener('keydown', onKey, true);
		return () => {
			clearTimeout(focus);
			document.removeEventListener('keydown', onKey, true);
		};
	}, [onClose, step]);

	const current = items[index];
	if (!current) return null;

	return (
		<Container spotlightId={CONTAINER_ID} className={css.viewer}>
			<Stage className={css.stage}>
				<img key={current.FilePath} className={css.image} src={srcFor(current)} alt="" />
			</Stage>
			<div className={css.bar + (chrome ? '' : ' ' + css.hidden)}>
				<div className={css.title}>{titleFor(current)}</div>
				<div className={css.count}>{index + 1} / {items.length}</div>
				<div className={css.hint}>◀ ▶ blättern · Zurück schließt</div>
			</div>
		</Container>
	);
};

ImageViewer.propTypes = {
	items: PropTypes.array.isRequired,
	onClose: PropTypes.func.isRequired,
	srcFor: PropTypes.func.isRequired,
	startIndex: PropTypes.number.isRequired,
	titleFor: PropTypes.func.isRequired
};

export default ImageViewer;
