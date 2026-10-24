import {useState} from 'react';
import PropTypes from 'prop-types';

/**
 * Großes Hintergrundbild: erst das Standbild in voller Größe (`poster`),
 * scheitert es, das kleine Vorschaubild (`fallback`). So bleibt ein Bild
 * stehen, auch wenn ffmpeg auf dem Server einmal nicht kann.
 *
 * Gemerkt wird, *welche* Adressen scheiterten — ein neues Standbild bekommt
 * wieder eine Chance.
 */
const Backdrop = ({poster, fallback, className}) => {
	const [failed, setFailed] = useState([]);
	const src = [poster, fallback].find(s => s && !failed.includes(s));
	// Beide gescheitert: kein kaputtes Bild, der Hintergrund dahinter bleibt.
	if (!src) return null;
	return <img className={className} src={src} alt="" onError={() => setFailed(f => [...f, src])} />;
};

Backdrop.propTypes = {
	className: PropTypes.string,
	fallback: PropTypes.string,
	poster: PropTypes.string
};

export default Backdrop;
