#include <vector>
#include <string>
#include <iostream>
#include <stdio.h>

#define START_FINAL_STATES 16
#define FAIL_STATE 19
#define STATE_TOKENID_DIFFERENCE 15

/*
  maps the ASCII values of the DFA alphabet to their respective index

  @charToIndex: pointer to the array where the values will be mapped

  Return: none
*/
void mapSymbols(int charToIndex[128])
{
  // any characters out of the alphabet
  for (int i = 0; i < 128; i++)
    charToIndex[i] = 9;

  // A-Z
  for (int i = 'A'; i < 'Z'; i++)
    charToIndex[i] = 8;

  // a-z
  for (int i = 'a'; i < 'z'; i++)
    charToIndex[i] = 8;

  charToIndex['_'] = 8;

  // 0-9
  for (int i = '0'; i < '9'; i++)
    charToIndex[i] = 8;

  charToIndex['\n'] = 0;
  charToIndex['d'] = 1;
  charToIndex['e'] = 2;
  charToIndex['f'] = 3;
  charToIndex['c'] = 4;
  charToIndex['l'] = 5;
  charToIndex['a'] = 6;
  charToIndex['s'] = 7;

  charToIndex[EOF] = 10;
  charToIndex['#'] = 11;
}

/*
  Determines if the DFA should consume the next character

  @state: current state
  @ch: current character

  e.g.
  if we have reached a delimiter for a lexeme, it will be consumed if it is a space,
  but it will be kept if it is a semicolon

  Return: 1 if it should advance, 0 if not
*/
int advance(int state, char ch)
{
  // return ch != EOF && (state != 17) && (state != 18) &&
  //        (state != START_FINAL_STATES ||
  //         (state == START_FINAL_STATES && ch == ' ')) &&
  //        !(state == 19 && ch == '\n');
  // return (state != 10)
  return state < START_FINAL_STATES && ch != '\0';
}

/*
  Determines if a state is accepted

  @state: current state

  states 12-17 are accepted

  Return: 1 if it is accepted, 0 if not
*/
int accept(int state)
{
  return state >= START_FINAL_STATES && state < FAIL_STATE;
}

/*
  Gets the token id based on the state

  @state: final state
  @buffer: buffer that stores the lexeme

  Return: token id
*/
int getTokenId(int state)
{
  return state - STATE_TOKENID_DIFFERENCE;
}

/*
 * Is a compiled shared library to be called from Python.
 * This function analyzes a code snippet and determines the programming paradigm.
 * It returns a string indicating the paradigm.
 * Possible return values:
 * - "Procedural Programming"
 * - "Object-Oriented Programming"
 * - "Procedural and Object-Oriented Programming"
 * - "Simple Text"
 *
 * @param code_snippet: A string containing the actual code snippet to analyze.
 * @return: A string indicating the programming paradigm.
 */
std::vector<int> scanner(const char *filename)
{
  const int transitionTable[16][12] = {
      {0, 4, 1, 1, 7, 1, 1, 12, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 12, 1, 2, 19, 3},
      {0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 19, 3},
      {0, 1, 5, 1, 1, 1, 1, 1, 1, 1, 19, 3},
      {0, 1, 1, 6, 1, 1, 1, 1, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 1, 1, 16, 16, 3},
      {0, 1, 1, 1, 1, 8, 1, 1, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 9, 1, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 10, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 11, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 1, 1, 17, 17, 3},
      {0, 1, 13, 1, 1, 1, 1, 1, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 14, 1, 1, 1, 1, 19, 3},
      {0, 1, 1, 15, 1, 1, 1, 1, 1, 1, 19, 3},
      {0, 1, 1, 1, 1, 1, 1, 1, 1, 18, 18, 18},
  };

  int charToIndex[128];
  mapSymbols(charToIndex);

  std::vector<int> tokens;

  int state;
  FILE *fileptr = fopen(filename, "r");
  char ch = fgetc(fileptr);
  int charVal = charToIndex[ch];
  int tokenid;

  int pp = 0;
  int oop = 0;

  // Main DFA simulation loop
  while (ch != EOF)
  {
    state = 0;
    // states >= START_FINAL_STATES are final
    while (state < START_FINAL_STATES)
    {
      state = transitionTable[state][charVal];
      if (advance(state, ch))
      {
        ch = fgetc(fileptr);
        if (ch == -1)
          charVal = 10;
        else
          charVal = charToIndex[ch];
      }
    }

    if (accept(state))
    {
      tokenid = getTokenId(state);
      tokens.push_back(tokenid);
    }
  }

  // Return the paradigm classification
  return tokens;
}

class Parser
{
  std::vector<int> tokens;
  int position = 0;
  bool isOOP = false;
  bool isPP = false;

  void match(int token)
  {
    if (token == tokens[position])
      position++;
    else
      error();
  }

  void error()
  {
    throw std::runtime_error("\nerror at position " + std::to_string(position) + "\n");
  }

  // S -> OOP | PP
  void S()
  {
    if (tokens[position] == 1)
      PP();
    else if (tokens[position] == 2 || tokens[position] == 3)
      OOP();
    else
      error();
  };

  // OOP -> class COMP | self COMP
  void OOP()
  {
    this->isOOP = true;

    if (tokens[position] == 2)
    {
      match(2);
      COMP();
    }
    else if (tokens[position] == 3)
    {
      match(3);
      COMP();
    }
    else
    {
      error();
    }
  }

  // PP -> def COMP
  void PP()
  {
    this->isPP = true;

    match(1);
    COMP();
  };

  // COMP -> OOP | PP | e
  void COMP()
  {
    if (tokens[position] == 1)
      PP();
    else if (tokens[position] == 2 || tokens[position] == 3)
      OOP();

    // epsilon production
    else if (tokens[position] == -1)
      return;
    else
      error();
  };

public:
  Parser(std::vector<int> tokens)
  {
    this->tokens = tokens;
  }

  std::string parse()
  {
    try
    {
      S();
    }
    catch (std::runtime_error e)
    {
      // prints where the error happened
      std::cout << e.what();
    }
    if (isOOP && isPP)
      return "Procedural and Object-Oriented Programming";
    else if (isOOP)
      return "Object-Oriented Programming";
    else if (isPP)
      return "Procedural Programming";
    else
      return "";
  }
};

int main()
{
  std::vector<int> tokens = scanner("3.py");
  tokens.push_back(-1);

  // 1: def, 2: class, 3: self, -1: $
  std::cout << "tokens: ";
  for (int token : tokens)
    std::cout << token << " ";

  Parser parser = Parser(tokens);
  std::string paradigm = parser.parse();
  std::cout << "\n\nParadigm: " << paradigm << "\n\n";
}