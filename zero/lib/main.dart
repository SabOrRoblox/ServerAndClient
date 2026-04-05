import 'package:flutter/material.dart';
import 'dart:math';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:confetti/confetti.dart';
import 'dart:async';

void main() {
  runApp(const TicTacToeApp());
}

class TicTacToeApp extends StatelessWidget {
  const TicTacToeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'tic-tac-toe',
      theme: ThemeData(
        brightness: Brightness.dark,
        primarySwatch: Colors.purple,
        scaffoldBackgroundColor: Colors.black,
        fontFamily: 'Poppins',
      ),
      debugShowCheckedModeBanner: false,
      home: const GamePage(),
    );
  }
}

class GamePage extends StatefulWidget {
  const GamePage({super.key});

  @override
  State<GamePage> createState() => _GamePageState();
}

class _GamePageState extends State<GamePage> with TickerProviderStateMixin {
  late List<String> board;
  bool isPlayerTurn = true;
  String message = 'your move';
  int scorePlayer = 0;
  int scoreBot = 0;
  int currentRound = 1;
  
  late ConfettiController _confettiController;
  late AnimationController _glowController;
  late AnimationController _pulseController;
  late AnimationController _shakeController;
  
  List<int> winningCombination = [];
  bool gameEnded = false;
  
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    _resetBoard();
    _confettiController = ConfettiController(duration: const Duration(seconds: 3));
    
    _glowController = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    )..repeat(reverse: true);
    
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    )..repeat();
    
    _shakeController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );
  }

  @override
  void dispose() {
    _confettiController.dispose();
    _glowController.dispose();
    _pulseController.dispose();
    _shakeController.dispose();
    super.dispose();
  }

  void _resetBoard() {
    setState(() {
      board = List.filled(9, '');
      isPlayerTurn = true;
      gameEnded = false;
      winningCombination = [];
      message = 'your move';
      if (!isPlayerTurn) {
        _botMove();
      }
    });
  }

  void _newRound() {
    setState(() {
      board = List.filled(9, '');
      isPlayerTurn = true;
      gameEnded = false;
      winningCombination = [];
      message = '✨ РАУНД ${currentRound + 1} ✨';
      currentRound++;
    });
    Future.delayed(const Duration(milliseconds: 1000), () {
      setState(() {
        message = '✨ ТВОЙ ХОД ✨';
      });
    });
  }

  void _makeMove(int index) async {
    if (!isPlayerTurn || board[index] != '' || gameEnded) return;

    // Анимация нажатия
    await _shakeController.forward();
    _shakeController.reset();

    setState(() {
      board[index] = 'X';
    });

    String? winner = _checkWinner();
    if (winner != null) {
      _endGame(winner);
      return;
    }

    if (_isBoardFull()) {
      _endGame('draw');
      return;
    }

    setState(() {
      isPlayerTurn = false;
      message = '🤖 ХОД БОТА 🤖';
    });

    // Задержка перед ходом бота для драматизма
    Future.delayed(const Duration(milliseconds: 600), _botMove);
  }

  void _botMove() {
    if (gameEnded) return;
    
    int index = _getBestMove();
    
    if (index != -1) {
      setState(() {
        board[index] = 'O';
      });

      String? winner = _checkWinner();
      if (winner != null) {
        _endGame(winner);
        return;
      }

      if (_isBoardFull()) {
        _endGame('draw');
        return;
      }

      setState(() {
        isPlayerTurn = true;
        message = '✨ ТВОЙ ХОД ✨';
      });
    }
  }

  int _getBestMove() {
    // 1. Победа бота
    for (int i = 0; i < 9; i++) {
      if (board[i] == '') {
        board[i] = 'O';
        if (_checkWinner() == 'O') {
          board[i] = '';
          return i;
        }
        board[i] = '';
      }
    }

    // 2. Блокировка игрока
    for (int i = 0; i < 9; i++) {
      if (board[i] == '') {
        board[i] = 'X';
        if (_checkWinner() == 'X') {
          board[i] = '';
          return i;
        }
        board[i] = '';
      }
    }

    // 3. Центр
    if (board[4] == '') return 4;

    // 4. Углы
    List<int> corners = [0, 2, 6, 8];
    List<int> availableCorners = corners.where((i) => board[i] == '').toList();
    if (availableCorners.isNotEmpty) {
      return availableCorners[_random.nextInt(availableCorners.length)];
    }

    // 5. Любой свободный
    List<int> available = [];
    for (int i = 0; i < 9; i++) {
      if (board[i] == '') available.add(i);
    }
    return available.isNotEmpty ? available[_random.nextInt(available.length)] : -1;
  }

  bool _isBoardFull() {
    return board.every((cell) => cell != '');
  }

  String? _checkWinner() {
    List<List<int>> winPatterns = [
      [0, 1, 2], [3, 4, 5], [6, 7, 8],
      [0, 3, 6], [1, 4, 7], [2, 5, 8],
      [0, 4, 8], [2, 4, 6]
    ];

    for (var pattern in winPatterns) {
      String a = board[pattern[0]];
      String b = board[pattern[1]];
      String c = board[pattern[2]];
      if (a != '' && a == b && b == c) {
        winningCombination = pattern;
        return a;
      }
    }
    return null;
  }

  void _endGame(String winner) async {
    gameEnded = true;
    
    if (winner == 'X') {
      scorePlayer++;
      message = '🎉 ПОБЕДА! 🎉';
      _confettiController.play();
      await Future.delayed(const Duration(seconds: 3));
      _confettiController.stop();
    } else if (winner == 'O') {
      scoreBot++;
      message = '😢 БОТ ПОБЕДИЛ 😢';
    } else {
      message = '🤝 НИЧЬЯ 🤝';
    }

    setState(() {});

    await Future.delayed(const Duration(seconds: 2));
    
    if (scorePlayer >= 5 || scoreBot >= 5) {
      _showGameOverDialog();
    } else {
      _newRound();
    }
  }

  void _showGameOverDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.grey[900],
        title: Text(
          scorePlayer > scoreBot ? '🏆 ТЫ ПОБЕДИЛ! 🏆' : '💀 БОТ ПОБЕДИЛ 💀',
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        content: Text(
          'ФИНАЛЬНЫЙ СЧЕТ: ${scorePlayer} : ${scoreBot}',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 20, color: Colors.white70),
        ),
        actions: [
          Center(
            child: ElevatedButton(
              onPressed: () {
                setState(() {
                  scorePlayer = 0;
                  scoreBot = 0;
                  currentRound = 1;
                });
                _resetBoard();
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.purple,
                padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 15),
              ),
              child: const Text('НОВАЯ ИГРА', style: TextStyle(fontSize: 18)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCell(int index) {
    bool isWinning = winningCombination.contains(index);
    
    return GestureDetector(
      onTap: () => _makeMove(index),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.elasticOut,
        margin: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          gradient: isWinning
              ? const LinearGradient(
                  colors: [Colors.green, Colors.lightGreen],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                )
              : LinearGradient(
                  colors: board[index] != ''
                      ? [Colors.grey[800]!, Colors.grey[900]!]
                      : [Colors.grey[850]!, Colors.grey[900]!],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: isWinning
              ? [
                  BoxShadow(
                    color: Colors.green.withOpacity(0.6),
                    blurRadius: 20,
                    spreadRadius: 5,
                  )
                ]
              : [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.5),
                    blurRadius: 10,
                    offset: const Offset(0, 5),
                  )
                ],
          border: Border.all(
            color: isWinning ? Colors.green : Colors.purple.withOpacity(0.3),
            width: 2,
          ),
        ),
        child: Center(
          child: TweenAnimationBuilder(
            duration: const Duration(milliseconds: 400),
            tween: Tween<double>(begin: 0, end: 1),
            builder: (context, double value, child) {
              return Transform.scale(
                scale: value,
                child: child,
              );
            },
            child: board[index] == 'X'
                ? Icon(
                    Icons.close,
                    size: 60,
                    color: Colors.cyanAccent,
                    shadows: const [
                      Shadow(blurRadius: 10, color: Colors.cyanAccent)
                    ],
                  )
                : board[index] == 'O'
                    ? Icon(
                        Icons.circle_outlined,
                        size: 55,
                        color: Colors.pinkAccent,
                        shadows: const [
                          Shadow(blurRadius: 10, color: Colors.pinkAccent)
                        ],
                      )
                    : const SizedBox(),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.center,
            radius: 1.5,
            colors: [
              Color(0xFF1a0033),
              Color(0xFF000000),
            ],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // Верхняя панель с анимацией
              AnimatedBuilder(
                animation: _glowController,
                builder: (context, child) {
                  return Container(
                    margin: const EdgeInsets.all(20),
                    padding: const EdgeInsets.symmetric(vertical: 15, horizontal: 20),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Colors.purple.withOpacity(0.3 + _glowController.value * 0.3),
                          Colors.pink.withOpacity(0.3 + _glowController.value * 0.3),
                        ],
                      ),
                      borderRadius: BorderRadius.circular(30),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.2),
                        width: 1,
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _buildScoreCard('ТЫ', scorePlayer, Icons.emoji_emotions, Colors.cyan),
                        _buildScoreCard('БОТ', scoreBot, Icons.memory, Colors.pink),
                      ],
                    ),
                  );
                },
              ),
              
              // Сообщение
              AnimatedOpacity(
                opacity: 1.0,
                duration: const Duration(milliseconds: 500),
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 10),
                  padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 15),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Colors.purple, Colors.deepPurple],
                    ),
                    borderRadius: BorderRadius.circular(50),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.purple.withOpacity(0.5),
                        blurRadius: 20,
                      ),
                    ],
                  ),
                  child: Text(
                    message,
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 2,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              
              // Игровое поле
              Expanded(
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(30),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.purple.withOpacity(0.3),
                              blurRadius: 50,
                              spreadRadius: 10,
                            ),
                          ],
                        ),
                        child: GridView.builder(
                          physics: const NeverScrollableScrollPhysics(),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 3,
                            childAspectRatio: 1,
                          ),
                          itemCount: 9,
                          itemBuilder: (context, index) => _buildCell(index),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              
              // Кнопка сброса
              Padding(
                padding: const EdgeInsets.all(20),
                child: AnimatedBuilder(
                  animation: _pulseController,
                  builder: (context, child) {
                    return ElevatedButton(
                      onPressed: () {
                        setState(() {
                          scorePlayer = 0;
                          scoreBot = 0;
                          currentRound = 1;
                        });
                        _resetBoard();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.transparent,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 15),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(30),
                          side: BorderSide(
                            color: Colors.white.withOpacity(0.5),
                            width: 2,
                          ),
                        ),
                        elevation: 10,
                        shadowColor: Colors.purple,
                      ),
                      child: Text(
                        'НОВАЯ ИГРА',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 2,
                          color: Colors.white.withOpacity(0.5 + _pulseController.value * 0.3),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildScoreCard(String title, int score, IconData icon, Color color) {
    return Column(
      children: [
        Icon(icon, color: color, size: 30),
        const SizedBox(height: 5),
        Text(
          title,
          style: TextStyle(
            fontSize: 16,
            color: Colors.white70,
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          '$score',
          style: TextStyle(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: color,
            shadows: [
              Shadow(blurRadius: 10, color: color),
            ],
          ),
        ),
      ],
    );
  }
}
