# AssetHold Tech Stack

## Core Technologies

### Language & Runtime
- **Python** 3.9+ - Primary development language
- **Poetry** - Dependency management and packaging

### Application Architecture
- **Modular Architecture** - Separate modules for stocks, real estate, portfolio management
- **Router Pattern** - Central engine with module-specific routers
- **YAML Configuration** - Flexible configuration management

### Data & Analysis Libraries
- **assetutilities** - Custom utility library for common operations
- **pandas** (implied) - Data manipulation and analysis
- **Financial Data APIs** - Multiple data source integrations
- **Technical Analysis Libraries** - For indicators and calculations

### Development Tools
- **pytest** - Testing framework
- **black** - Code formatting
- **isort** - Import sorting
- **mypy** - Static type checking
- **bumpver** - Version management

### Project Structure
```
assethold/
├── src/assethold/
│   ├── engine.py           # Core engine with router pattern
│   ├── modules/
│   │   ├── stocks/         # Stock analysis module
│   │   ├── fixed_interest/ # Fixed income analysis
│   │   └── portfolio/      # Portfolio management
│   ├── common/             # Shared utilities
│   └── legacy_code/        # Legacy Flask application
├── tests/                  # Comprehensive test suite
├── docs/                   # Documentation and resources
└── data/                   # Sample data and datasets
```

### Configuration Management
- **YAML Files** - Primary configuration format
- **AttributeDict** - Dynamic configuration access
- **Environment-based** - Support for different environments

### Data Storage
- **CSV Files** - Historical data storage
- **JSON Files** - Company tickers and metadata
- **File-based** - Local file system for data persistence

### Testing Strategy
- **Unit Tests** - Module-level testing
- **Integration Tests** - End-to-end analysis testing
- **YAML Test Fixtures** - Reusable test configurations
- **Results Validation** - Output comparison and verification

### Version Control
- **Git** - Source control
- **GitHub** - Repository hosting
- **Feature Branches** - Development workflow

### Build & Distribution
- **Poetry Build System** - Package building
- **setuptools** - Legacy support
- **PyPI** - Package distribution (planned)

## Development Standards

### Code Style
- PEP 8 compliant
- Black formatting
- Type hints where applicable
- Docstrings for public methods

### Module Organization
- Clear separation of concerns
- Reusable components
- Consistent naming conventions
- Minimal coupling between modules