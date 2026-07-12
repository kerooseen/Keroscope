from ui.main_window import MainWindow


def main() -> None:
    """Entry point for the KeroScope application without a console window."""
    window = MainWindow()
    window.run()


if __name__ == "__main__":
    main()
