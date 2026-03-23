// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface ISeriousCustomer {
    function isSeriousCustomer(address) external view returns (bool);
}

/// @title VulnAuction — English auction for zero-day exploits
/// @notice Seller sets reserve price and duration. Bidders place increasing bids.
///         Optionally restricted to Serious Customers only. Uses pull pattern for
///         outbid refunds. Settlement splits 90% seller / 10% platform.
contract VulnAuction is ReentrancyGuard {
    enum State { Active, Ended, Settled, Cancelled }

    address public immutable seller;
    address public immutable operator;
    address public immutable platform;
    ISeriousCustomer public immutable scContract;

    uint256 public immutable reservePrice;
    uint256 public immutable endTime;
    bool    public immutable scOnly;
    uint256 public constant PLATFORM_FEE_BPS = 1000; // 10%

    State   public state;
    address public highestBidder;
    uint256 public highestBid;

    mapping(address => uint256) public pendingReturns;

    // ── Events ──

    event BidPlaced(address indexed bidder, uint256 amount);
    event AuctionEnded(address indexed winner, uint256 amount);
    event AuctionSettled(uint256 sellerPayout, uint256 platformFee);
    event AuctionCancelled();
    event Withdrawal(address indexed bidder, uint256 amount);

    // ── Modifiers ──

    modifier onlySeller()     { require(msg.sender == seller,   "Only seller");   _; }
    modifier inState(State s) { require(state == s,             "Wrong state");   _; }

    // ── Constructor ──

    constructor(
        address _seller,
        address _operator,
        address _platform,
        address _scContract,
        uint256 _reservePrice,
        uint256 _duration,
        bool    _scOnly
    ) {
        require(_seller   != address(0), "Invalid seller");
        require(_operator != address(0), "Invalid operator");
        require(_platform != address(0), "Invalid platform");
        require(!_scOnly || _scContract != address(0), "SC contract required");
        require(_reservePrice > 0,       "Reserve must be positive");
        require(_duration > 0,           "Duration must be positive");

        seller       = _seller;
        operator     = _operator;
        platform     = _platform;
        scContract   = ISeriousCustomer(_scContract);
        reservePrice = _reservePrice;
        endTime      = block.timestamp + _duration;
        scOnly       = _scOnly;
        state        = State.Active;
    }

    // ── Bidding ──

    /// @notice Place a bid. Must exceed current highest bid and reserve price.
    function bid() external payable inState(State.Active) nonReentrant {
        require(block.timestamp < endTime, "Auction ended");
        require(msg.value > highestBid,    "Bid too low");
        require(msg.value >= reservePrice, "Below reserve");

        if (scOnly) {
            require(scContract.isSeriousCustomer(msg.sender), "SC only");
        }

        if (highestBidder != address(0)) {
            pendingReturns[highestBidder] += highestBid;
        }

        highestBidder = msg.sender;
        highestBid    = msg.value;

        emit BidPlaced(msg.sender, msg.value);
    }

    /// @notice Withdraw funds from being outbid.
    function withdraw() external nonReentrant {
        uint256 amount = pendingReturns[msg.sender];
        require(amount > 0, "Nothing to withdraw");

        pendingReturns[msg.sender] = 0;

        emit Withdrawal(msg.sender, amount);

        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "Withdrawal failed");
    }

    // ── Lifecycle ──

    /// @notice Anyone can end the auction after endTime.
    function endAuction() external {
        require(block.timestamp >= endTime, "Not ended yet");
        require(state == State.Active,      "Wrong state");

        state = State.Ended;

        emit AuctionEnded(highestBidder, highestBid);
    }

    /// @notice Seller settles the auction — pays out 90/10 split.
    function settle() external onlySeller inState(State.Ended) nonReentrant {
        require(highestBidder != address(0), "No bids");

        state = State.Settled;

        uint256 fee          = (highestBid * PLATFORM_FEE_BPS) / 10000;
        uint256 sellerPayout = highestBid - fee;

        emit AuctionSettled(sellerPayout, fee);

        (bool s1, ) = seller.call{value: sellerPayout}("");
        require(s1, "Seller payout failed");

        (bool s2, ) = platform.call{value: fee}("");
        require(s2, "Platform fee failed");
    }

    /// @notice Seller cancels — only if no bids placed yet.
    function cancel() external onlySeller inState(State.Active) nonReentrant {
        require(highestBidder == address(0), "Has bids");

        state = State.Cancelled;

        emit AuctionCancelled();
    }
}
