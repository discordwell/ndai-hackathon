// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VerificationDeposit — Anti-spam deposits for 0day verification marketplace
/// @notice Sellers deposit ETH before submitting a PoC. The TEE operator refunds
///         honest sellers and forfeits spam deposits to the platform pool.
///         Sellers can also purchase or earn permanent trust badges.
contract VerificationDeposit is ReentrancyGuard {
    address public immutable operator;  // TEE operator — can refund/forfeit/grant badges
    address public immutable platform;  // Receives forfeited deposits + badge purchases

    uint256 public constant BADGE_PRICE = 0.04 ether; // ~$100 at ETH ~$2500

    struct Deposit {
        address seller;
        uint256 amount;
        bool settled; // true once refunded or forfeited
    }

    mapping(bytes32 => Deposit) public deposits;
    mapping(address => bool) public hasBadge;
    mapping(bytes32 => uint256) public platformEscrow; // keccak256("linux") => required deposit

    uint256 public platformBalance; // accumulated forfeited deposits + badge purchases

    // ── Events ──

    event Deposited(bytes32 indexed proposalId, address indexed seller, uint256 amount);
    event Refunded(bytes32 indexed proposalId, address indexed seller, uint256 amount);
    event Forfeited(bytes32 indexed proposalId, address indexed seller, uint256 amount);
    event BadgePurchased(address indexed buyer, uint256 price);
    event BadgeGranted(address indexed seller);
    event PlatformEscrowSet(bytes32 indexed platformKey, uint256 amount);

    // ── Modifiers ──

    modifier onlyOperator() {
        require(msg.sender == operator, "Only operator");
        _;
    }

    // ── Constructor ──

    constructor(address _operator, address _platform) {
        require(_operator != address(0), "Invalid operator");
        require(_platform != address(0), "Invalid platform");
        operator = _operator;
        platform = _platform;
    }

    // ── Deposit lifecycle ──

    /// @notice Seller deposits ETH for a proposal. Amount must meet platform-specific minimum.
    /// @param proposalId Unique identifier for the vulnerability proposal
    function deposit(bytes32 proposalId) external payable {
        require(deposits[proposalId].seller == address(0), "Already deposited");

        uint256 required = platformEscrow[proposalId];
        if (required == 0) {
            required = BADGE_PRICE;
        }
        require(msg.value >= required, "Insufficient deposit");

        deposits[proposalId] = Deposit({
            seller: msg.sender,
            amount: msg.value,
            settled: false
        });

        emit Deposited(proposalId, msg.sender, msg.value);
    }

    /// @notice Operator refunds a deposit to the seller (PoC was valid).
    /// @param proposalId Proposal to refund
    function refund(bytes32 proposalId) external onlyOperator nonReentrant {
        Deposit storage d = deposits[proposalId];
        require(d.seller != address(0), "No deposit");
        require(!d.settled, "Already settled");

        d.settled = true;
        uint256 amount = d.amount;
        address seller = d.seller;

        emit Refunded(proposalId, seller, amount);

        (bool ok, ) = seller.call{value: amount}("");
        require(ok, "Refund transfer failed");
    }

    /// @notice Operator forfeits a deposit (PoC was invalid/spam). Funds go to platform pool.
    /// @param proposalId Proposal to forfeit
    function forfeit(bytes32 proposalId) external onlyOperator nonReentrant {
        Deposit storage d = deposits[proposalId];
        require(d.seller != address(0), "No deposit");
        require(!d.settled, "Already settled");

        d.settled = true;
        uint256 amount = d.amount;

        platformBalance += amount;

        emit Forfeited(proposalId, d.seller, amount);
    }

    // ── Badge system ──

    /// @notice Anyone can purchase a permanent trust badge.
    function purchaseBadge() external payable {
        require(!hasBadge[msg.sender], "Already has badge");
        require(msg.value >= BADGE_PRICE, "Insufficient payment");

        hasBadge[msg.sender] = true;
        platformBalance += msg.value;

        emit BadgePurchased(msg.sender, msg.value);
    }

    /// @notice Operator grants a free badge to a verified seller.
    /// @param seller Address to grant badge to
    function grantBadge(address seller) external onlyOperator {
        require(!hasBadge[seller], "Already has badge");
        hasBadge[seller] = true;
        emit BadgeGranted(seller);
    }

    // ── Platform configuration ──

    /// @notice Operator sets required deposit amount per platform.
    /// @param platformKey keccak256 of platform name (e.g., keccak256("linux"))
    /// @param amount Required deposit in wei
    function setPlatformEscrow(bytes32 platformKey, uint256 amount) external onlyOperator {
        platformEscrow[platformKey] = amount;
        emit PlatformEscrowSet(platformKey, amount);
    }

    // ── Withdrawals ──

    /// @notice Operator withdraws accumulated platform fees to the platform address.
    function withdrawPlatformFees() external onlyOperator nonReentrant {
        uint256 amount = platformBalance;
        require(amount > 0, "No fees to withdraw");

        platformBalance = 0;

        (bool ok, ) = platform.call{value: amount}("");
        require(ok, "Withdraw transfer failed");
    }
}
