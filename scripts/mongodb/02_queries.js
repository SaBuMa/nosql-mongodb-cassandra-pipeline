// -----------------------------------------------------------------------------
// Tasks 2-4 - MongoDB queries (server version 4.4)
//
// Run inside the Mongo shell, or from bash with:
//   mongosh --host mongo -u root --authenticationDatabase admin -p --file scripts/mongodb/02_queries.js
// -----------------------------------------------------------------------------

db = db.getSiblingDB("entertainment");

// Sanity check: the import loaded every document
print("Total documents: " + db.movies.countDocuments());            // 100

// -----------------------------------------------------------------------------
// Task 2 - Year in which the most movies were released
//
// Pipeline: GROUP by year -> COUNT per group -> SORT desc -> LIMIT
// Notes:
//   * {$sum: 1} counts documents. {$sum: "$year"} would ADD the year values
//     (2016 x 73 = 147168), a bug caught during the project by sanity-checking
//     against the 100-document total.
//   * The {$count: {}} accumulator inside $group only exists from MongoDB 5.0;
//     on a 4.4 server it raises "unknown group operator '$count'".
//   * $limit 3 instead of 1 makes ties visible.
// -----------------------------------------------------------------------------
print("\nTask 2 - Movies per year (top 3):");
db.movies.aggregate([
  { $group: { _id: "$year", movie_count: { $sum: 1 } } },
  { $sort:  { movie_count: -1 } },
  { $limit: 3 }
]).forEach(printjson);
// { _id: 2016, movie_count: 73 }
// { _id: 2015, movie_count: 8 }
// { _id: 2014, movie_count: 5 }

// Cross-check with an independent method
print("Cross-check 2016: " + db.movies.countDocuments({ year: 2016 }));   // 73

// -----------------------------------------------------------------------------
// Task 3 - Count of movies released after 1999 (1999 excluded -> $gt)
// Two independent methods; both must agree.
// -----------------------------------------------------------------------------
print("\nTask 3 - Movies released after 1999:");
print("countDocuments: " + db.movies.countDocuments({ year: { $gt: 1999 } }));   // 99

db.movies.aggregate([
  { $match: { year: { $gt: 1999 } } },
  { $count: "movies_after_1999" }      // the $count STAGE exists in 4.4
]).forEach(printjson);                 // { movies_after_1999: 99 }

// -----------------------------------------------------------------------------
// Task 4 - Average votes for movies released in 2007
//
// Pipeline: FILTER first ($match), then ONE group for everything that passed.
// Notes:
//   * year is stored as a number: {year: "2007"} (a string) matches nothing.
//   * Field names are case-sensitive: "$Votes", not "$votes". $avg over a
//     missing field returns null silently, with no error.
// -----------------------------------------------------------------------------
print("\nTask 4 - Average votes in 2007:");
db.movies.aggregate([
  { $match: { year: 2007 } },
  { $group: { _id: "$year", averageVotes: { $avg: "$Votes" } } }
]).forEach(printjson);
// { _id: 2007, averageVotes: 192.5 }

// Show what the average is built on (only 2 documents!)
db.movies.find({ year: 2007 }, { _id: 1, title: 1, Votes: 1 }).forEach(printjson);
