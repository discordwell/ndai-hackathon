// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@chainlink/v0.8/shared/interfaces/AggregatorV3Interface.sol";

/// @title SeriousCustomer — Refundable $5K USD deposit for marketplace buyers
/// @notice Buyers deposit ETH equivalent of $5,000 USD (via Chainlink price feed) to
///         prove seriousness. The deposit is refunded on the buyer's first deal >= $50K.
///         Verified exploit publishers are auto-granted SC status by the operator.
contract SeriousCustomer is ReentrancyGuard {
    address public immutable operator;
    address public immutable platform;
    AggregatorV3Interface public immutable priceFeed;

    uint256 public constant TARGET_USD = 5_000;         // $5,000 deposit
    uint256 public constant REFUND_THRESHOLD_USD = 50_000; // $50K deal minimum
    uint256 public constant PRICE_STALENESS = 24 hours; // relaxed for testnet

    mapping(address => bool) public isSeriousCustomer;
    mapping(address => uint256) public depositOf;
    mapping(address => bool) public hasBeenRefunded;

    // ── Events ──

    event SeriousCustomerDeposited(address indexed buyer, uint256 amount, uint256 ethPriceUsd);
    event SeriousCustomerRefunded(address indexed buyer, uint256 amount);
    event SeriousCustomerGranted(address indexed user);

    // ── Modifiers ──

    modifier onlyOperator() {
        require(msg.sender == operator, "Only operator");
        _;
    }

    // ── Constructor ──

    constructor(address _operator, address _platform, address _priceFeed) {
        require(_operator != address(0), "Invalid operator");
        require(_platform != address(0), "Invalid platform");
        require(_priceFeed != address(0), "Invalid price feed");
        operator = _operator;
        platform = _platform;
        priceFeed = AggregatorV3Interface(_priceFeed);
    }

    // ── Price helpers ──

    /// @notice Returns the latest ETH/USD price from Chainlink (8 decimals).
    function getLatestPrice() public view returns (uint256) {
        (, int256 price, , uint256 updatedAt, ) = priceFeed.latestRoundData();
        require(price > 0, "Invalid price");
        require(block.timestamp - updatedAt < PRICE_STALENESS, "Stale price");
        return uint256(price);
    }

    /// @notice Returns the minimum ETH (in wei) needed for a $5,000 deposit.
    function getMinDepositWei() public view returns (uint256) {
        uint256 price = getLatestPrice(); // 8 decimals
        // TARGET_USD * 1e8 * 1e18 / price  →  wei
        return (TARGET_USD * 1e8 * 1e18) / price;
    }

    // ── Deposit ──

    /// @notice Buyer deposits ETH >= $5,000 USD equivalent to become a Serious Customer.
    function deposit() external payable {
        require(!isSeriousCustomer[msg.sender], "Already SC");
        uint256 minWei = getMinDepositWei();
        require(msg.value >= minWei, "Insufficient deposit");

        isSeriousCustomer[msg.sender] = true;
        depositOf[msg.sender] = msg.value;

        emit SeriousCustomerDeposited(msg.sender, msg.value, getLatestPrice());
    }

    // ── Refund (operator) ──

    /// @notice Operator refunds the deposit after buyer's first deal >= $50K.
    /// @param buyer Address to refund
    function refundDeposit(address buyer) external onlyOperator nonReentrant {
        require(isSeriousCustomer[buyer], "Not SC");
        require(!hasBeenRefunded[buyer], "Already refunded");
        uint256 amount = depositOf[buyer];
        require(amount > 0, "No deposit to refund");

        hasBeenRefunded[buyer] = true;

        emit SeriousCustomerRefunded(buyer, amount);

        (bool ok, ) = buyer.call{value: amount}("");
        require(ok, "Refund failed");
    }

    // ── Grant (operator) ──

    /// @notice Operator grants SC status to verified exploit publishers (no deposit needed).
    /// @param user Address to grant
    function grantSeriousCustomer(address user) external onlyOperator {
        require(!isSeriousCustomer[user], "Already SC");
        isSeriousCustomer[user] = true;
        emit SeriousCustomerGranted(user);
    }
}
