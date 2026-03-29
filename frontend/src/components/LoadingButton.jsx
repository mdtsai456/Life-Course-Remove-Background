export default function LoadingButton({
  type = 'button',
  loading,
  loadingText,
  children,
  spinnerStyle,
  ...rest
}) {
  return (
    <button type={type} {...rest}>
      {loading ? (
        <span className="spinner-wrapper">
          <span className="spinner" style={spinnerStyle} />
          {loadingText}
        </span>
      ) : (
        children
      )}
    </button>
  )
}
