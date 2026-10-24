import PropTypes from 'prop-types';

import css from './Brand.module.less';

/**
 * Schriftzug „ARCADE“ im Markenverlauf — das Logo in der Kopfleiste und auf
 * dem Login.
 *
 * @param {string} [size] - 'normal' (Kopfleiste) oder 'large' (Login, Laden)
 */
const Brand = ({size = 'normal'}) => (
	<div className={css.brand + (size === 'large' ? ' ' + css.large : '')} aria-label="Arcade">
		ARCADE
	</div>
);

Brand.propTypes = {
	size: PropTypes.oneOf(['normal', 'large'])
};

export default Brand;
