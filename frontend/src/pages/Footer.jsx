export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-top">
          <div className="footer-about">
            <div className="brand footer-brand">DataClean</div>
            <p className="footer-note">
              Upload a spreadsheet. Get clean data, a dashboard, and an AI summary.
            </p>
          </div>

          <div className="footer-contact">
            <span className="contact-number">Contact: </span>
            <span className="contact-number">+998 90 6450007</span>
          </div>
        </div>

        <div className="footer-bottom">
          <span className="footer-year mono">© 2026 DataClean</span>
        </div>
      </div>
</footer>
  )
}